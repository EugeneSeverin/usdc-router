import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.collector.collector import collect_once
from app.config import get_settings
from app.db import sessionmaker

log = logging.getLogger(__name__)


async def job() -> None:
    try:
        async with sessionmaker()() as s:
            n = await collect_once(s)
        log.info("collected %d protocols", n)
    except Exception:
        log.exception("collector failed")  # TODO: алерт команде (п.8: отставание >15 мин)


def start_scheduler() -> AsyncIOScheduler:
    sch = AsyncIOScheduler()
    sch.add_job(
        job,
        "interval",
        seconds=get_settings().collect_interval_seconds,
        id="collect",
        max_instances=1,
        coalesce=True,
    )
    sch.start()
    return sch
