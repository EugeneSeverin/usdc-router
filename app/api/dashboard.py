from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.charts.plotly_charts import apy_chart, spread_chart
from app.db import get_session
from app.i18n import pick_lang, translator
from app.services import rates
from app.services.calculator import calculate

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))

SORTS = {"apy", "tvl", "utilization", "network", "name", "ts"}
RANGES = {"1d": 1, "7d": 7, "30d": 30}


def _sort_key(col: str):
    def k(r: rates.RateRow):
        v = {
            "apy": r.apy,
            "tvl": r.tvl,
            "utilization": r.utilization,
            "network": r.network,
            "name": r.name,
            "ts": r.ts,
        }[col]
        return (v is None, v if not isinstance(v, (int, float)) else -v)

    return k


def _spread_series(series: dict[str, list]) -> list[tuple]:
    """Спред по времени: лучший Aptos минус лучший Solana по каждой метке времени."""
    from app.adapters.registry import load_adapters

    nets = {a.slug: a.network for a in load_adapters(only_active=False)}
    buckets: dict = {}
    for slug, pts in series.items():
        for ts, apy in pts:
            key = ts.replace(second=0, microsecond=0)
            b = buckets.setdefault(key, {"solana": None, "aptos": None})
            n = nets.get(slug)
            if n and (b[n] is None or apy > b[n]):
                b[n] = apy
    return [
        (k, b["aptos"] - b["solana"])
        for k, b in sorted(buckets.items())
        if b["aptos"] is not None and b["solana"] is not None
    ]


@router.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    session: AsyncSession = Depends(get_session),
    lang: str | None = None,
    sort: str = "apy",
    range: str = Query("7d"),
    amount: float = Query(1000, gt=0, le=1e9),
    days: int = Query(30, ge=1, le=3650),
):
    lang = pick_lang(lang, request.headers.get("accept-language"))
    sort = sort if sort in SORTS else "apy"
    range_ = range if range in RANGES else "7d"
    rows = sorted(await rates.latest_rows(session), key=_sort_key(sort))
    summary = rates.summarize(rows)
    series = await rates.history(session, RANGES[range_])
    nonce = request.state.nonce
    charts = {
        "apy": apy_chart(series, translator(lang)("chart_apy"), nonce) if series else "",
        "spread": "",
    }
    sp = _spread_series(series)
    if sp:
        charts["spread"] = spread_chart(sp, translator(lang)("chart_spread"), nonce)
    calc = None
    if summary.best_solana and summary.best_aptos:
        calc = calculate(amount, days, summary.best_solana.apy or 0, summary.best_aptos.apy or 0)
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "t": translator(lang),
            "lang": lang,
            "rows": rows,
            "summary": summary,
            "charts": charts,
            "calc": calc,
            "amount": amount,
            "days": days,
            "sort": sort,
            "range": range_,
            "nonce": nonce,
        },
    )
