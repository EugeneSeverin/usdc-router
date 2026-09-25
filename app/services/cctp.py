"""Клиент Circle CCTP V2 (Iris API). Только V2 (п.3 ТЗ)."""

import asyncio
from dataclasses import dataclass

import httpx

from app.config import cctp_config, get_settings

DOMAINS = {"solana": 5, "aptos": 9}


class CctpError(Exception):
    pass


class AttestationPending(CctpError):
    """Attestation ещё не готова — повторить позже (не ошибка, деньги в безопасности)."""


@dataclass(slots=True)
class Attestation:
    message: str  # hex, 0x...
    attestation: str  # hex, 0x...
    nonce: str | None
    status: str


def iris_base() -> str:
    c = cctp_config()["iris"]
    return c["mainnet"] if get_settings().network_mode == "mainnet" else c["testnet"]


def domain(network: str) -> int:
    return DOMAINS[network]


class IrisClient:
    def __init__(self, client: httpx.AsyncClient | None = None, base_url: str | None = None):
        self._client = client or httpx.AsyncClient(timeout=20)
        self._base = (base_url or iris_base()).rstrip("/")

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get_attestation(self, src_network: str, burn_tx_hash: str) -> Attestation:
        """GET /v2/messages/{srcDomain}?transactionHash=... — единственный источник attestation."""
        url = f"{self._base}/v2/messages/{domain(src_network)}"
        try:
            r = await self._client.get(url, params={"transactionHash": burn_tx_hash})
        except httpx.HTTPError as e:
            raise CctpError(f"iris unreachable: {e}") from e
        if r.status_code == 404:
            raise AttestationPending("message not indexed yet")
        if r.status_code >= 400:
            raise CctpError(f"iris {r.status_code}: {r.text[:200]}")
        messages = r.json().get("messages") or []
        if not messages:
            raise AttestationPending("no messages yet")
        m = messages[0]
        if m.get("status") != "complete" or not m.get("attestation") or m["attestation"] == "PENDING":
            raise AttestationPending(f"status={m.get('status')}")
        return Attestation(
            message=m["message"], attestation=m["attestation"], nonce=m.get("eventNonce"), status="complete"
        )

    async def wait_attestation(
        self, src_network: str, burn_tx_hash: str, timeout: float = 900, interval: float = 5
    ) -> Attestation:
        waited = 0.0
        while True:
            try:
                return await self.get_attestation(src_network, burn_tx_hash)
            except AttestationPending:
                if waited >= timeout:
                    raise
                await asyncio.sleep(interval)
                waited += interval

    async def burn_fee_bps(self, src_network: str, dst_network: str) -> float:
        """GET /v2/burn/USDC/fees/{src}/{dst} -> комиссия быстрого перевода в bps (minimumFee)."""
        url = f"{self._base}/v2/burn/USDC/fees/{domain(src_network)}/{domain(dst_network)}"
        try:
            r = await self._client.get(url)
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise CctpError(f"iris fee: {e}") from e
        for tier in r.json():
            if tier.get("finalityThreshold") == 1000:  # fast
                return float(tier["minimumFee"])
        raise CctpError("no fast-transfer fee tier")
