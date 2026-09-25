"""Telegram-бот: /start /rates /alert <п.п.> /stop. Запуск: python -m app.bot.telegram_bot"""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy import select

from app.bot.alerts import check_and_send
from app.config import get_settings
from app.db import init_models, sessionmaker
from app.models import TgSubscriber
from app.services import rates

log = logging.getLogger(__name__)
dp = Dispatcher()
DEFAULT_THRESHOLD = 1.0


async def _sub(session, chat_id: int) -> TgSubscriber:
    sub = await session.get(TgSubscriber, chat_id)
    if sub is None:
        sub = TgSubscriber(chat_id=chat_id, spread_threshold=DEFAULT_THRESHOLD)
        session.add(sub)
    return sub


@dp.message(Command("start"))
async def start(m: Message):
    async with sessionmaker()() as s:
        sub = await _sub(s, m.chat.id)
        sub.active = True
        await s.commit()
    await m.answer(
        "USDC Router: алерты о спреде ставок Solana/Aptos.\n"
        "/rates — текущие ставки\n/alert <п.п.> — порог спреда (сейчас по умолчанию 1.0)\n/stop — отписаться"
    )


@dp.message(Command("rates"))
async def cmd_rates(m: Message):
    async with sessionmaker()() as s:
        rows = await rates.latest_rows(s)
    lines = [
        f"{r.network:6} {r.name}: " + (f"{r.apy:.2f}%" if r.apy is not None else "нет данных")
        for r in rows
    ]
    sm = rates.summarize(rows)
    if sm.spread is not None:
        lines.append(f"\nСпред: {abs(sm.spread):.2f} п.п. ({'Aptos' if sm.spread > 0 else 'Solana'} выгоднее)")
    lines.append(get_settings().base_url)
    await m.answer("\n".join(lines))


@dp.message(Command("alert"))
async def cmd_alert(m: Message, command: CommandObject):
    try:
        v = float((command.args or "").replace(",", "."))
        if not 0 < v <= 50:
            raise ValueError
    except ValueError:
        await m.answer("Использование: /alert 1.5 — порог спреда в п.п. (0–50)")
        return
    async with sessionmaker()() as s:
        sub = await _sub(s, m.chat.id)
        sub.spread_threshold, sub.active, sub.above_since = v, True, None
        await s.commit()
    await m.answer(f"Порог: {v:.2f} п.п. Алерт придёт, если спред держится выше порога 30 минут.")


@dp.message(Command("stop"))
async def stop(m: Message):
    async with sessionmaker()() as s:
        sub = await s.get(TgSubscriber, m.chat.id)
        if sub:
            sub.active = False
            await s.commit()
    await m.answer("Вы отписаны. /start — подписаться снова.")


async def notify(bot: Bot, chat_id: int, text: str) -> None:
    try:
        await bot.send_message(chat_id, text)
    except Exception:
        log.exception("send failed to %s", chat_id)


async def alert_loop(bot: Bot, every: int = 300) -> None:
    while True:
        try:
            async with sessionmaker()() as s:
                await check_and_send(s, lambda c, t: notify(bot, c, t), get_settings().base_url)
        except Exception:
            log.exception("alert loop")
        await asyncio.sleep(every)


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    token = get_settings().telegram_token
    if not token:
        raise SystemExit("TELEGRAM_TOKEN не задан")
    await init_models()
    bot = Bot(token)
    task = asyncio.create_task(alert_loop(bot))
    try:
        await dp.start_polling(bot)
    finally:
        task.cancel()


if __name__ == "__main__":
    asyncio.run(main())


__all__ = ["select"]
