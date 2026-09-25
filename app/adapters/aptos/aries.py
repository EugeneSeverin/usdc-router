from app.adapters.generic import AggregatorBackedAdapter


class AriesAdapter(AggregatorBackedAdapter):
    """Aries Markets. Нет пула на DefiLlama -> нужен on-chain адаптер через view-функции Move."""
