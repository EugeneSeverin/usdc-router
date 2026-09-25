from app.adapters.generic import AggregatorBackedAdapter


class MarginFiAdapter(AggregatorBackedAdapter):
    """MarginFi. Нет пула на DefiLlama -> get_rates даёт DataUnavailable до on-chain адаптера (Bank USDC через IDL)."""
