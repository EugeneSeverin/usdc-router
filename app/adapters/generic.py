from app.adapters.base import (
    DataUnavailable,
    NotImplementedOnChain,
    Position,
    ProtocolAdapter,
    RateData,
    TxPayload,
)
from app.adapters.defillama import fetch_pool_rates


class AggregatorBackedAdapter(ProtocolAdapter):
    """Ставки — из DefiLlama до появления on-chain декодера.

    Позиции и сборка транзакций (этап 2) — per-protocol, реализуются в подклассах;
    пока они честно бросают NotImplementedError, а не подделывают транзакции.
    """

    async def get_rates(self) -> RateData:
        return await fetch_pool_rates(self.defillama_pool_id)

    async def get_user_position(self, address: str) -> Position:
        raise NotImplementedError(f"{self.slug}: get_user_position (этап 2, неделя 4-5)")

    async def build_withdraw_tx(self, address: str, amount_usdc: float) -> TxPayload:
        raise NotImplementedError(f"{self.slug}: build_withdraw_tx (этап 2)")

    async def build_deposit_tx(self, address: str, amount_usdc: float) -> TxPayload:
        raise NotImplementedError(f"{self.slug}: build_deposit_tx (этап 2)")


__all__ = ["AggregatorBackedAdapter", "DataUnavailable", "NotImplementedOnChain"]
