"""Минимальный словарь ru/en (п.8: интерфейс на двух языках)."""

STRINGS: dict[str, dict[str, str]] = {
    "ru": {
        "title": "USDC Router",
        "tagline": "Где USDC приносит больше: Solana или Aptos",
        "best_solana": "Лучшая ставка Solana",
        "best_aptos": "Лучшая ставка Aptos",
        "spread": "Спред",
        "direction_to_aptos": "выгоднее Aptos",
        "direction_to_solana": "выгоднее Solana",
        "no_data": "нет данных",
        "network": "Сеть",
        "protocol": "Протокол",
        "apy": "APY",
        "apy_base": "база",
        "apy_rewards": "награды",
        "tvl": "Депозиты",
        "utilization": "Утилизация",
        "updated": "Обновлено",
        "questionable": "данные под вопросом",
        "chart_apy": "APY по протоколам",
        "chart_spread": "Спред Aptos − Solana (п.п.)",
        "calculator": "Калькулятор",
        "amount": "Сумма, USDC",
        "days": "Срок, дней",
        "calc": "Посчитать",
        "income_solana": "Доход в Solana",
        "income_aptos": "Доход в Aptos",
        "transfer_cost": "Стоимость перевода",
        "gain": "Чистый выигрыш от переноса",
        "breakeven_days": "Окупаемость, дней",
        "breakeven_amount": "Окупается от суммы",
        "not_worth": "При таких параметрах перенос убыточен",
        "risk": "Риски DeFi: ставки не гарантированы, протоколы могут быть взломаны или "
        "приостановлены. Не инвестируйте больше, чем готовы потерять.",
    },
    "en": {
        "title": "USDC Router",
        "tagline": "Where USDC earns more: Solana or Aptos",
        "best_solana": "Best Solana rate",
        "best_aptos": "Best Aptos rate",
        "spread": "Spread",
        "direction_to_aptos": "Aptos pays more",
        "direction_to_solana": "Solana pays more",
        "no_data": "no data",
        "network": "Network",
        "protocol": "Protocol",
        "apy": "APY",
        "apy_base": "base",
        "apy_rewards": "rewards",
        "tvl": "Deposits",
        "utilization": "Utilization",
        "updated": "Updated",
        "questionable": "data in question",
        "chart_apy": "APY by protocol",
        "chart_spread": "Spread Aptos − Solana (pp)",
        "calculator": "Calculator",
        "amount": "Amount, USDC",
        "days": "Term, days",
        "calc": "Calculate",
        "income_solana": "Income on Solana",
        "income_aptos": "Income on Aptos",
        "transfer_cost": "Transfer cost",
        "gain": "Net gain from moving",
        "breakeven_days": "Breakeven, days",
        "breakeven_amount": "Profitable from amount",
        "not_worth": "Moving is not profitable with these parameters",
        "risk": "DeFi risk: rates are not guaranteed; protocols can be hacked or paused. "
        "Do not invest more than you can afford to lose.",
    },
}


def pick_lang(lang: str | None, accept_language: str | None) -> str:
    if lang in STRINGS:
        return lang  # type: ignore[return-value]
    if accept_language and accept_language.lower().startswith("en"):
        return "en"
    return "ru"


def translator(lang: str):
    d = STRINGS[lang]
    return lambda k: d.get(k, k)
