import asyncio
import logging
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import DataUnavailable, NotImplementedOnChain, ProtocolAdapter, RateData
from app.adapters.registry import load_adapters
from app.config import get_settings, protocols_config
from app.models import Network, Protocol, RateSnapshot, utcnow

log = logging.getLogger(__name__)


async def sync_protocols(session: AsyncSession) -> dict[str, Protocol]:
    """Синхронизировать реестр protocols с config/protocols.yaml."""
    existing = {p.slug: p for p in (await session.scalars(select(Protocol))).all()}
    for c in protocols_config():
        p = existing.get(c["slug"])
        if p is None:
            p = Protocol(slug=c["slug"], network=Network(c["network"]), name=c["name"])
            session.add(p)
            existing[c["slug"]] = p
        p.name = c["name"]
        p.addresses = c.get("addresses", {})
        p.is_active = c.get("is_active", True)
    await session.commit()
    return existing


async def _fetch(adapter: ProtocolAdapter) -> tuple[RateData | None, RateData | None, str | None]:
    """(основной on-chain, резервный агрегатор, ошибка)."""
    primary = fallback = None
    err = None
    try:
        primary = await adapter.get_onchain_rates()
    except NotImplementedOnChain:
        pass
    except DataUnavailable as e:
        err = str(e)
    try:
        fallback = await adapter.get_rates()
    except DataUnavailable as e:
        err = err or str(e)
    return primary, fallback, err


async def _is_flagged(session: AsyncSession, protocol_id: int, diverged_now: bool) -> bool:
    """п.4.1: расхождение >1 п.п. держится 30 минут подряд -> «данные под вопросом».

    Замер помечается, если сейчас расхождение есть и все замеры за окно (покрывающее
    ~30 минут) тоже были с расхождением.
    """
    if not diverged_now:
        return False
    window = timedelta(minutes=get_settings().discrepancy_minutes)
    since = utcnow() - window
    rows = (
        await session.scalars(
            select(RateSnapshot)
            .where(RateSnapshot.protocol_id == protocol_id, RateSnapshot.ts >= since)
            .order_by(RateSnapshot.ts)
        )
    ).all()
    if not rows:
        return False
    covers_window = utcnow() - rows[0].ts.replace(tzinfo=rows[0].ts.tzinfo or utcnow().tzinfo) >= (
        window - timedelta(minutes=6)
    )
    return covers_window and all(r.diverged for r in rows)


async def collect_once(
    session: AsyncSession, adapters: list[ProtocolAdapter] | None = None
) -> int:
    protos = await sync_protocols(session)
    adapters = adapters if adapters is not None else load_adapters()
    results = await asyncio.gather(*(_fetch(a) for a in adapters))
    n = 0
    for a, (primary, fallback, err) in zip(adapters, results, strict=True):
        p = protos[a.slug]
        data = primary or fallback
        if data is None:
            session.add(
                RateSnapshot(protocol_id=p.id, error=(err or "no data")[:250], source="none")
            )
            log.warning("no data for %s: %s", a.slug, err)
            continue
        diverged = False
        if primary and fallback:
            diff = abs(
                (primary.apy_base or 0)
                + (primary.apy_rewards or 0)
                - (fallback.apy_base or 0)
                - (fallback.apy_rewards or 0)
            )
            diverged = diff > get_settings().discrepancy_pp
        flagged = await _is_flagged(session, p.id, diverged)
        session.add(
            RateSnapshot(
                protocol_id=p.id,
                apy_base=data.apy_base,
                apy_rewards=data.apy_rewards,
                tvl=data.tvl,
                utilization=data.utilization,
                available_liquidity=data.available_liquidity,
                source=data.source,
                flagged=flagged,
                diverged=diverged,
            )
        )
        n += 1
    await session.commit()
    return n
