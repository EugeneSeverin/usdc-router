from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.services import rates
from app.services.calculator import calculate

router = APIRouter(prefix="/api")


@router.get("/rates")
async def get_rates(session: AsyncSession = Depends(get_session)):
    rows = await rates.latest_rows(session)
    s = rates.summarize(rows)
    return {
        "protocols": [
            {
                "slug": r.slug,
                "name": r.name,
                "network": r.network,
                "apy": r.apy,
                "apy_base": r.apy_base,
                "apy_rewards": r.apy_rewards,
                "tvl": r.tvl,
                "utilization": r.utilization,
                "updated": r.ts,
                "flagged": r.flagged,
                "error": r.error,
            }
            for r in rows
        ],
        "best_solana": s.best_solana.slug if s.best_solana else None,
        "best_aptos": s.best_aptos.slug if s.best_aptos else None,
        "spread": s.spread,
        "direction": s.direction,
    }


@router.get("/history")
async def get_history(
    days: int = Query(7, ge=1, le=90), session: AsyncSession = Depends(get_session)
):
    h = await rates.history(session, days)
    return {slug: [{"ts": t, "apy": a} for t, a in pts] for slug, pts in h.items()}


@router.get("/calc")
async def calc(
    amount: float = Query(gt=0, le=1e9),
    days: int = Query(30, ge=1, le=3650),
    session: AsyncSession = Depends(get_session),
):
    s = rates.summarize(await rates.latest_rows(session))
    if not (s.best_solana and s.best_aptos):
        return {"error": "no data"}
    return calculate(amount, days, s.best_solana.apy or 0, s.best_aptos.apy or 0)


@router.get("/health")
async def health(session: AsyncSession = Depends(get_session)):
    rows = await rates.latest_rows(session)
    ts = [r.ts for r in rows if r.ts]
    return {"ok": True, "last_collected": max(ts) if ts else None}
