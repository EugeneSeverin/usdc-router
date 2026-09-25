from app.adapters.generic import AggregatorBackedAdapter


class ThalaAdapter(AggregatorBackedAdapter):
    """Thala. Нет пула на DefiLlama -> нужен on-chain адаптер."""
