"""Логика алертов (п.4.3): спред выше порога 30 минут подряд, не чаще раза в 6 часов."""

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TgSubscriber, utcnow
from app.services import rates

HOLD = timedelta(minutes=30)
COOLDOWN = timedelta(hours=6)


def _aware(dt: datetime | None) -> datetime | None:
    return dt.replace(tzinfo=utcnow().tzinfo) if dt and dt.tzinfo is None else dt


def evaluate(sub: TgSubscriber, abs_spread: float | None, now: datetime) -> bool:
    """Обновляет sub.above_since и возвращает True, если пора слать алерт."""
    if abs_spread is None or abs_spread < sub.spread_threshold:
        sub.above_since = None
        return False
    if sub.above_since is None:
        sub.above_since = now
    if now - _aware(sub.above_since) < HOLD:
        return False
    last = _aware(sub.last_alert_at)
    if last is not None and now - last < COOLDOWN:
        return False
    sub.last_alert_at = now
    return True


def format_alert(s: rates.Summary, dashboard_url: str, lang: str) -> str:
    assert s.best_solana and s.best_aptos and s.spread is not None
    to = "Aptos" if s.spread > 0 else "Solana"
    if lang == "en":
        return (
            f"📈 USDC spread {abs(s.spread):.2f} pp — {to} pays more\n"
            f"Solana: {s.best_solana.apy:.2f}% ({s.best_solana.name})\n"
            f"Aptos: {s.best_aptos.apy:.2f}% ({s.best_aptos.name})\n{dashboard_url}"
        )
    return (
        f"📈 Спред USDC {abs(s.spread):.2f} п.п. — выгоднее {to}\n"
        f"Solana: {s.best_solana.apy:.2f}% ({s.best_solana.name})\n"
        f"Aptos: {s.best_aptos.apy:.2f}% ({s.best_aptos.name})\n{dashboard_url}"
    )


async def check_and_send(session: AsyncSession, send, dashboard_url: str) -> int:
    """send(chat_id, text) — корутина отправки. Возвращает число отправленных алертов."""
    s = rates.summarize(await rates.latest_rows(session))
    spread = abs(s.spread) if s.spread is not None else None
    now = utcnow()
    sent = 0
    for sub in (await session.scalars(select(TgSubscriber).where(TgSubscriber.active))).all():
        if evaluate(sub, spread, now):
            await send(sub.chat_id, format_alert(s, dashboard_url, sub.lang))
            sent += 1
    await session.commit()
    return sent
