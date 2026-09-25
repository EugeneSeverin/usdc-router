"""Единый интерфейс адаптера протокола (п.7 ТЗ)."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


class DataUnavailable(Exception):
    """Источник не дал данных. Мы не подставляем выдуманные значения."""


class NotImplementedOnChain(DataUnavailable):
    """On-chain декодер для протокола ещё не написан (см. TODO в адаптере)."""


@dataclass(slots=True)
class RateData:
    apy_base: float | None  # % годовых
    apy_rewards: float | None
    tvl: float | None  # USD
    utilization: float | None = None  # 0..1
    available_liquidity: float | None = None  # USDC
    source: str = "defillama"


@dataclass(slots=True)
class Position:
    protocol_slug: str
    amount_usdc: float


@dataclass(slots=True)
class TxPayload:
    """Solana: base64 сериализованная транзакция. Aptos: entry-function payload (dict)."""

    network: str
    solana_tx_b64: str | None = None
    aptos_payload: dict[str, Any] | None = None


class ProtocolAdapter(ABC):
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.slug: str = config["slug"]
        self.network: str = config["network"]
        self.addresses: dict[str, Any] = config.get("addresses", {})
        self.defillama_pool_id: str | None = config.get("defillama_pool_id")

    @abstractmethod
    async def get_rates(self) -> RateData:
        """APY (база + награды), TVL, утилизация, ликвидность. Бросает DataUnavailable."""

    async def get_apy(self) -> float:
        r = await self.get_rates()
        return (r.apy_base or 0.0) + (r.apy_rewards or 0.0)

    async def get_tvl(self) -> float:
        r = await self.get_rates()
        if r.tvl is None:
            raise DataUnavailable("tvl")
        return r.tvl

    async def get_onchain_rates(self) -> RateData:
        """Основной источник (RPC/IDL). По умолчанию не реализован -> collector идёт в fallback."""
        raise NotImplementedOnChain(self.slug)

    @abstractmethod
    async def get_user_position(self, address: str) -> Position: ...

    @abstractmethod
    async def build_withdraw_tx(self, address: str, amount_usdc: float) -> TxPayload: ...

    @abstractmethod
    async def build_deposit_tx(self, address: str, amount_usdc: float) -> TxPayload: ...
