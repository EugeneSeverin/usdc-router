"""Конечный автомат перевода (п.5.2–5.4). Порядок шагов строго линейный, откаты запрещены."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Transfer, TransferStatus, utcnow

S = TransferStatus
ORDER = [S.created, S.withdrawn, S.burned, S.attested, S.minted, S.deposited]
TERMINAL = {S.deposited, S.minted_no_deposit, S.failed}

# failed допустим до сжигания; после сжигания деньги «в пути», и мы не помечаем перевод failed:
# он остаётся «зависшим» и завершается через «Завершить перевод».
ALLOWED: dict[S, set[S]] = {
    S.created: {S.withdrawn, S.burned, S.failed},  # withdrawn пропускается, если USDC уже на кошельке
    S.withdrawn: {S.burned, S.failed},
    S.burned: {S.attested},
    S.attested: {S.minted},
    S.minted: {S.deposited, S.minted_no_deposit},
    S.deposited: set(),
    S.minted_no_deposit: set(),
    S.failed: set(),
}


class TransferError(Exception):
    pass


def service_fee(amount: float) -> float:
    return round(amount * get_settings().service_fee_bps / 10_000, 6)


def validate_amount(amount: float) -> None:
    if amount < get_settings().min_transfer_usdc:
        raise TransferError(f"minimum transfer is {get_settings().min_transfer_usdc} USDC")


def advance(t: Transfer, new: TransferStatus) -> None:
    if new not in ALLOWED[t.status]:
        raise TransferError(f"illegal transition {t.status} -> {new}")
    t.status = new
    t.updated_at = utcnow()


def steps(t: Transfer) -> list[tuple[TransferStatus, bool]]:
    """Для экрана статуса: (шаг, выполнен ли)."""
    cur = ORDER.index(S.deposited if t.status == S.minted_no_deposit else t.status) if (
        t.status in ORDER or t.status == S.minted_no_deposit
    ) else 0
    return [(s, i <= cur) for i, s in enumerate(ORDER) if s != S.created]


def can_complete(t: Transfer) -> bool:
    """Кнопка «Завершить перевод»: сожжено, но не выпущено — данные сообщения CCTP хранятся."""
    return t.status in {S.burned, S.attested}


async def create_transfer(
    session: AsyncSession,
    *,
    direction: str,
    amount: float,
    solana_address: str | None,
    aptos_address: str | None,
    source_protocol: str | None = None,
    dest_protocol: str | None = None,
    reference: str | None = None,
) -> Transfer:
    if direction not in {"solana_to_aptos", "aptos_to_solana"}:
        raise TransferError("bad direction")
    validate_amount(amount)
    if not (solana_address and aptos_address):
        raise TransferError("both wallets must be connected")
    t = Transfer(
        direction=direction,
        amount_usdc=amount,
        solana_address=solana_address,
        aptos_address=aptos_address,
        source_protocol=source_protocol,
        dest_protocol=dest_protocol,
        reference=reference,
        fees={"service_fee_usdc": service_fee(amount)},
    )
    session.add(t)
    await session.commit()
    return t


async def record_burn(session: AsyncSession, t: Transfer, burn_tx_hash: str) -> None:
    """Сохранить хэш сожжения СРАЗУ — по нему восстанавливается перевод."""
    t.burn_tx_hash = burn_tx_hash
    if t.status == S.created:
        advance(t, S.withdrawn)
    advance(t, S.burned)
    await session.commit()


async def record_attestation(session: AsyncSession, t: Transfer, message: str, attestation: str,
                             nonce: str | None) -> None:
    t.cctp_message, t.cctp_attestation, t.cctp_nonce = message, attestation, nonce
    advance(t, S.attested)
    await session.commit()


async def by_wallet(session: AsyncSession, solana: str | None, aptos: str | None) -> list[Transfer]:
    """«Мои переводы»: только по кошелькам текущей сессии."""
    conds = []
    if solana:
        conds.append(Transfer.solana_address == solana)
    if aptos:
        conds.append(Transfer.aptos_address == aptos)
    if not conds:
        return []
    from sqlalchemy import or_

    q = select(Transfer).where(or_(*conds)).order_by(Transfer.created_at.desc())
    return list((await session.scalars(q)).all())
