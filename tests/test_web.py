import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.adapters.base import RateData
from app.api import dashboard, rates_api
from app.collector.collector import collect_once
from app.core.security import SecurityHeadersMiddleware
from app.db import get_session
from tests.test_collector import Fake


@pytest_asyncio.fixture
async def client(session):
    await collect_once(
        session,
        [
            Fake("kamino-lend-main", "solana", RateData(4.0, 0.5, 1e6)),
            Fake("echelon-market", "aptos", RateData(1.0, 5.0, 2e6)),
        ],
    )
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)
    app.include_router(rates_api.router)
    app.include_router(dashboard.router)

    async def _s():
        yield session

    app.dependency_overrides[get_session] = _s
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        yield c


async def test_api_rates(client):
    j = (await client.get("/api/rates")).json()
    assert j["spread"] == 1.5 and j["direction"] == "solana_to_aptos"


async def test_index_renders_ru_and_en_with_csp(client):
    r = await client.get("/")
    assert r.status_code == 200
    assert "Лучшая ставка Solana" in r.text and "Риски DeFi" in r.text
    assert "script-src 'self' 'nonce-" in r.headers["content-security-policy"]
    en = await client.get("/?lang=en")
    assert "Best Solana rate" in en.text


async def test_sort_and_calc_params_validated(client):
    assert (await client.get("/?sort=apy&amount=5000&days=60")).status_code == 200
    assert (await client.get("/?amount=-1")).status_code == 422
    assert (await client.get("/?sort=<script>")).status_code == 200  # неизвестная сортировка -> apy


__all__ = ["async_sessionmaker"]
