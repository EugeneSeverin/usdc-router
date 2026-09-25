import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.api import dashboard, rates_api, transfers, wallets
from app.collector.scheduler import job, start_scheduler
from app.config import get_settings
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
app.add_middleware(
    SessionMiddleware,
    secret_key=get_settings().secret_key,
    https_only=get_settings().base_url.startswith("https"),
    same_site="lax",
)
app.mount(
    "/static", StaticFiles(directory=str(Path(__file__).resolve().parent / "static")), name="static"
)
app.include_router(rates_api.router)
app.include_router(wallets.router)
app.include_router(transfers.router)
app.include_router(dashboard.router)
