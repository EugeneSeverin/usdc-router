"""Мини-клиент Solana JSON-RPC с переключением на резервный узел (п.8: failover)."""

import httpx

from app.config import get_settings


class RpcError(Exception):
    pass


async def rpc(method: str, params: list, client: httpx.AsyncClient | None = None):
    own = client is None
    client = client or httpx.AsyncClient(timeout=10)
    last: Exception | None = None
    try:
        for url in get_settings().solana_rpcs:  # основной, затем резервные
            try:
                r = await client.post(url, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
                r.raise_for_status()
                body = r.json()
                if "error" in body:
                    raise RpcError(str(body["error"]))
                return body["result"]
            except (httpx.HTTPError, RpcError) as e:
                last = e
        raise RpcError(f"all solana rpcs failed: {last}")
    finally:
        if own:
            await client.aclose()


async def find_signature_by_reference(reference: str, client: httpx.AsyncClient | None = None) -> str | None:
    """Solana Pay: транзакцию с ключом-меткой reference находим по getSignaturesForAddress.

    Возвращает подпись только успешной (err is None) транзакции.
    """
    sigs = await rpc(
        "getSignaturesForAddress", [reference, {"limit": 5, "commitment": "confirmed"}], client
    )
    for s in sigs:
        if s.get("err") is None:
            return s["signature"]
    return None
