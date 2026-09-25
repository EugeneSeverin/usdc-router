import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import dashboard, rates_api
from app.collector.scheduler import job, start_scheduler
from app.core.security import SecurityHeadersMiddleware
from app.db import init_models

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_models()  # в проде схему ведёт Alembic; create_all идемпотентен
    sch = start_scheduler()
    await job()  # первый сбор сразу, чтобы дашборд не был пустым
    yield
    sch.shutdown(wait=False)


app = FastAPI(title="USDC Router", lifespan=lifespan)
app.add_middleware(SecurityHeadersMiddleware)
app.mount(
    "/static", StaticFiles(directory=str(Path(__file__).resolve().parent / "static")), name="static"
)
app.include_router(rates_api.router)
app.include_router(dashboard.router)
