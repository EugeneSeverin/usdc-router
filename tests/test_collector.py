from app.adapters.base import DataUnavailable, NotImplementedOnChain, ProtocolAdapter, RateData
from app.collector.collector import collect_once
from app.services import rates


class Fake(ProtocolAdapter):
    def __init__(self, slug, network, fallback=None, primary=None, err=None):
        super().__init__({"slug": slug, "network": network})
        self._fb, self._pr, self._err = fallback, primary, err

    async def get_onchain_rates(self):
        if self._pr is None:
            raise NotImplementedOnChain(self.slug)
        return self._pr

    async def get_rates(self):
        if self._err:
            raise DataUnavailable(self._err)
        return self._fb

    async def get_user_position(self, address): ...
    async def build_withdraw_tx(self, address, amount_usdc): ...
    async def build_deposit_tx(self, address, amount_usdc): ...


async def test_collect_summary_and_missing_data(session, monkeypatch):
    # slug должен быть в protocols.yaml, чтобы sync_protocols создал запись
    adapters = [
        Fake("kamino-lend-main", "solana", RateData(4.0, 0.5, 1e6)),
        Fake("echelon-market", "aptos", RateData(1.0, 5.0, 2e6)),
        Fake("marginfi", "solana", err="no defillama pool configured"),
    ]
    n = await collect_once(session, adapters)
    assert n == 2  # marginfi без данных: пишем ошибку, а не выдуманное число

    rows = {r.slug: r for r in await rates.latest_rows(session)}
    assert rows["marginfi"].apy is None
    assert rows["marginfi"].error == "no defillama pool configured"

    s = rates.summarize(list(rows.values()))
    assert s.best_solana.slug == "kamino-lend-main"
    assert s.best_aptos.slug == "echelon-market"
    assert s.spread == 1.5
    assert s.direction == "solana_to_aptos"


async def test_divergence_recorded(session):
    a = Fake(
        "kamino-lend-main",
        "solana",
        RateData(4.0, 0, 1),
        primary=RateData(7.0, 0, 1, source="onchain"),
    )
    await collect_once(session, [a])
    from sqlalchemy import select

    from app.models import RateSnapshot

    snap = (await session.scalars(select(RateSnapshot))).one()
    assert snap.diverged and snap.source == "onchain"
    assert not snap.flagged  # одного замера мало: нужны 30 минут подряд
