"""Калькулятор дохода и порога окупаемости (п.4.2)."""

from dataclasses import dataclass

from app.config import get_settings

# Оценки комиссий; точные значения подставляются при сборке перевода (этап 2).
EST_GAS_SOLANA_USD = 0.05
EST_GAS_APTOS_USD = 0.05
CCTP_FAST_FEE_BPS = 1.0  # быстрый перевод из Solana; уточняется по Circle fee API


@dataclass(slots=True)
class CalcResult:
    income_solana: float
    income_aptos: float
    transfer_cost: float
    gain: float  # выигрыш от переноса в лучшую сеть за срок, за вычетом комиссий
    breakeven_days: float | None
    breakeven_amount: float | None  # сумма, при которой перенос окупается за выбранный срок
    profitable: bool


def _var_bps(from_network: str) -> float:
    s = get_settings()
    return s.service_fee_bps + (CCTP_FAST_FEE_BPS if from_network == "solana" else 0.0)


def transfer_cost(amount: float, from_network: str) -> float:
    return amount * _var_bps(from_network) / 10_000 + EST_GAS_SOLANA_USD + EST_GAS_APTOS_USD


def calculate(amount: float, days: int, apy_solana: float, apy_aptos: float) -> CalcResult:
    inc_s = amount * apy_solana / 100 * days / 365
    inc_a = amount * apy_aptos / 100 * days / 365
    from_net = "solana" if apy_aptos >= apy_solana else "aptos"
    cost = transfer_cost(amount, from_net)
    gain = abs(inc_a - inc_s) - cost
    daily_per_usd = abs(apy_aptos - apy_solana) / 100 / 365
    be_days = cost / (amount * daily_per_usd) if amount > 0 and daily_per_usd > 0 else None
    var = _var_bps(from_net) / 10_000
    fixed = EST_GAS_SOLANA_USD + EST_GAS_APTOS_USD
    be_amount = fixed / (daily_per_usd * days - var) if daily_per_usd * days > var else None
    return CalcResult(inc_s, inc_a, cost, gain, be_days, be_amount, gain > 0)
