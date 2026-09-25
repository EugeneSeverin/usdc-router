from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Network, Protocol, RateSnapshot, utcnow


@dataclass(slots=True)
class RateRow:
    slug: str
    name: str
    network: str
    apy_base: float | None
    apy_rewards: float | None
    tvl: float | None
    utilization: float | None
    ts: datetime | None
    flagged: bool
    error: str | None

    @property
    def apy(self) -> float | None:
        if self.apy_base is None and self.apy_rewards is None:
            return None
        return (self.apy_base or 0.0) + (self.apy_rewards or 0.0)


@dataclass(slots=True)
class Summary:
    best_solana: RateRow | None
    best_aptos: RateRow | None
    spread: float | None  # п.п.; >0 => Aptos выгоднее
    direction: str | None  # solana_to_aptos | aptos_to_solana


async def latest_rows(session: AsyncSession) -> list[RateRow]:
    rows: list[RateRow] = []
    for p in (await session.scalars(select(Protocol).where(Protocol.is_active))).all():
        s = await session.scalar(
            select(RateSnapshot)
            .where(RateSnapshot.protocol_id == p.id)
            .order_by(RateSnapshot.ts.desc())
            .limit(1)
        )
        rows.append(
            RateRow(
                p.slug,
                p.name,
                p.network.value,
                s.apy_base if s else None,
                s.apy_rewards if s else None,
                s.tvl if s else None,
                s.utilization if s else None,
                s.ts if s else None,
                bool(s and s.flagged),
                s.error if s else "no data yet",
            )
        )
    return rows


def summarize(rows: list[RateRow]) -> Summary:
    def best(net: str) -> RateRow | None:
        c = [r for r in rows if r.network == net and r.apy is not None and not r.flagged]
        return max(c, key=lambda r: r.apy or 0) if c else None

    sol, apt = best(Network.solana.value), best(Network.aptos.value)
    if sol and apt:
        spread = (apt.apy or 0) - (sol.apy or 0)
        return Summary(sol, apt, spread, "solana_to_aptos" if spread > 0 else "aptos_to_solana")
    return Summary(sol, apt, None, None)


async def history(session: AsyncSession, days: int) -> dict[str, list[tuple[datetime, float]]]:
    since = utcnow() - timedelta(days=days)
    out: dict[str, list[tuple[datetime, float]]] = {}
    q = (
        select(Protocol.slug, RateSnapshot.ts, RateSnapshot.apy_base, RateSnapshot.apy_rewards)
        .join(RateSnapshot, RateSnapshot.protocol_id == Protocol.id)
        .where(RateSnapshot.ts >= since, RateSnapshot.error.is_(None))
        .order_by(RateSnapshot.ts)
    )
    for slug, ts, b, r in (await session.execute(q)).all():
        out.setdefault(slug, []).append((ts, (b or 0) + (r or 0)))
    return out
