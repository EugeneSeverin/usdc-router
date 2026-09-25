from app.adapters.generic import AggregatorBackedAdapter


class KaminoAdapter(AggregatorBackedAdapter):
    """Kamino Lend. TODO: on-chain — декодировать Reserve через anchorpy + IDL klend, APY из кривой утилизации."""
