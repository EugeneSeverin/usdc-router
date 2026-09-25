import pytest

from app.services.calculator import calculate, transfer_cost


def test_income_and_gain():
    r = calculate(10_000, 365, apy_solana=4.0, apy_aptos=8.0)
    assert r.income_solana == pytest.approx(400)
    assert r.income_aptos == pytest.approx(800)
    assert r.gain == pytest.approx(400 - transfer_cost(10_000, "solana"))
    assert r.profitable


def test_unprofitable_small_amount_short_term():
    r = calculate(20, 7, apy_solana=4.0, apy_aptos=4.5)
    assert not r.profitable
    assert r.breakeven_amount is None  # спред за 7 дней не покрывает даже переменную комиссию


def test_breakeven_amount_is_actually_breakeven():
    days, a_s, a_a = 30, 3.0, 9.0
    r = calculate(1000, days, a_s, a_a)
    assert r.breakeven_amount is not None
    at = calculate(r.breakeven_amount, days, a_s, a_a)
    assert at.gain == pytest.approx(0, abs=1e-6)


def test_direction_aptos_to_solana_uses_no_cctp_fast_fee():
    assert transfer_cost(1000, "aptos") < transfer_cost(1000, "solana")
