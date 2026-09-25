import httpx

from app.adapters.base import DataUnavailable, RateData
from app.config import get_settings


async def fetch_pool_rates(pool_id: str | None, client: httpx.AsyncClient | None = None) -> RateData:
    """Данные пула с DefiLlama Yields (резервный источник, п.4.1)."""
    if not pool_id:
        raise DataUnavailable("no defillama pool configured")
    base = get_settings().defillama_yields_url
    own = client is None
    client = client or httpx.AsyncClient(timeout=15)
    try:
        r = await client.get(f"{base}/chart/{pool_id}")
        r.raise_for_status()
        points = r.json().get("data") or []
    except httpx.HTTPError as e:
        raise DataUnavailable(f"defillama: {e}") from e
    finally:
        if own:
            await client.aclose()
    if not points:
        raise DataUnavailable("defillama: empty chart")
    last = points[-1]
    return RateData(
        apy_base=last.get("apyBase"),
        apy_rewards=last.get("apyReward"),
        tvl=last.get("tvlUsd"),
        source="defillama",
    )
