import enum
from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class Network(enum.StrEnum):
    solana = "solana"
    aptos = "aptos"


class TransferStatus(enum.StrEnum):
    """Шаги из п.5.2: Выведено → Сожжено → Подтверждено Circle → Выпущено → Внесено."""

    created = "created"
    withdrawn = "withdrawn"
    burned = "burned"
    attested = "attested"
    minted = "minted"
    deposited = "deposited"  # финал
    minted_no_deposit = "minted_no_deposit"  # финал: депозит отклонён, USDC на кошельке (п.5.3)
    failed = "failed"


class Protocol(Base):
    __tablename__ = "protocols"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    network: Mapped[Network] = mapped_column(Enum(Network))
    name: Mapped[str] = mapped_column(String(64))
    addresses: Mapped[dict] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class RateSnapshot(Base):
    __tablename__ = "rate_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    protocol_id: Mapped[int] = mapped_column(ForeignKey("protocols.id"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    apy_base: Mapped[float | None] = mapped_column(Float)
    apy_rewards: Mapped[float | None] = mapped_column(Float)
    tvl: Mapped[float | None] = mapped_column(Float)
    utilization: Mapped[float | None] = mapped_column(Float)
    available_liquidity: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(16), default="defillama")  # onchain | defillama
    flagged: Mapped[bool] = mapped_column(Boolean, default=False)  # «данные под вопросом»
    diverged: Mapped[bool] = mapped_column(Boolean, default=False)  # замер расходится с резервом
    error: Mapped[str | None] = mapped_column(String(256))  # нет данных — не выдумываем


class Transfer(Base):
    __tablename__ = "transfers"

    id: Mapped[int] = mapped_column(primary_key=True)
    solana_address: Mapped[str | None] = mapped_column(String(64), index=True)
    aptos_address: Mapped[str | None] = mapped_column(String(80), index=True)
    direction: Mapped[str] = mapped_column(String(20))  # solana_to_aptos | aptos_to_solana
    source_protocol: Mapped[str | None] = mapped_column(String(64))
    dest_protocol: Mapped[str | None] = mapped_column(String(64))
    amount_usdc: Mapped[float] = mapped_column(Float)
    status: Mapped[TransferStatus] = mapped_column(
        Enum(TransferStatus), default=TransferStatus.created, index=True
    )
    reference: Mapped[str | None] = mapped_column(String(64), index=True)  # Solana Pay reference
    burn_tx_hash: Mapped[str | None] = mapped_column(String(100))
    mint_tx_hash: Mapped[str | None] = mapped_column(String(100))
    deposit_tx_hash: Mapped[str | None] = mapped_column(String(100))
    cctp_message: Mapped[str | None] = mapped_column(String)  # hex; нужен для «Завершить перевод»
    cctp_attestation: Mapped[str | None] = mapped_column(String)
    cctp_nonce: Mapped[str | None] = mapped_column(String(80))
    fees: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class TgSubscriber(Base):
    __tablename__ = "tg_subscribers"

    chat_id: Mapped[int] = mapped_column(primary_key=True)
    spread_threshold: Mapped[float] = mapped_column(Float, default=1.0)  # п.п.
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    above_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_alert_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lang: Mapped[str] = mapped_column(String(2), default="ru")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


__all__ = ["Base", "Integer"]
