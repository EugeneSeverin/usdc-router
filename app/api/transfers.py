from html import escape
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.i18n import pick_lang, translator
from app.models import Transfer, TransferStatus
from app.services import cctp, transfers

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


def _ctx(request: Request, **kw):
    lang = pick_lang(request.query_params.get("lang"), request.headers.get("accept-language"))
    return {"t": translator(lang), "lang": lang, "nonce": request.state.nonce, **kw}


async def _own(session: AsyncSession, request: Request, transfer_id: int) -> Transfer:
    """Доступ только к переводам кошельков из текущей сессии."""
    t = await session.get(Transfer, transfer_id)
    s = request.session
    if t is None or not (
        (s.get("solana") and t.solana_address == s.get("solana"))
        or (s.get("aptos") and t.aptos_address == s.get("aptos"))
    ):
        raise HTTPException(404, "transfer not found")
    return t


@router.post("/transfer")
async def create(
    request: Request,
    direction: str = Form(...),
    amount: float = Form(..., gt=0, le=1e9),
    source_protocol: str | None = Form(None),
    dest_protocol: str | None = Form(None),
    session: AsyncSession = Depends(get_session),
):
    s = request.session
    try:
        t = await transfers.create_transfer(
            session,
            direction=direction,
            amount=amount,
            solana_address=s.get("solana"),
            aptos_address=s.get("aptos"),
            source_protocol=source_protocol,
            dest_protocol=dest_protocol,
        )
    except transfers.TransferError as e:
        raise HTTPException(400, str(e)) from e
    return RedirectResponse(f"/transfer/{t.id}", status_code=303)


@router.get("/transfer/{transfer_id}", response_class=HTMLResponse)
async def status(request: Request, transfer_id: int, session: AsyncSession = Depends(get_session)):
    t = await _own(session, request, transfer_id)
    done = t.status in transfers.TERMINAL
    return templates.TemplateResponse(
        request,
        "transfer.html",
        _ctx(request, t_=t, steps=transfers.steps(t), can_complete=transfers.can_complete(t),
             refresh=None if done else 10, escape=escape),
    )


@router.post("/transfer/{transfer_id}/complete")
async def complete(request: Request, transfer_id: int, session: AsyncSession = Depends(get_session)):
    """«Завершить перевод»: повторно берём attestation по хэшу сожжения (деньги не теряются)."""
    t = await _own(session, request, transfer_id)
    if not transfers.can_complete(t):
        raise HTTPException(409, "nothing to complete")
    if not t.burn_tx_hash:
        raise HTTPException(409, "no burn tx recorded")
    src = "solana" if t.direction == "solana_to_aptos" else "aptos"
    client = cctp.IrisClient()
    try:
        att = await client.get_attestation(src, t.burn_tx_hash)
    except cctp.AttestationPending:
        return RedirectResponse(f"/transfer/{t.id}?pending=1", status_code=303)
    except cctp.CctpError as e:
        raise HTTPException(502, str(e)) from e
    finally:
        await client.aclose()
    if t.status == TransferStatus.burned:
        await transfers.record_attestation(session, t, att.message, att.attestation, att.nonce)
    return RedirectResponse(f"/transfer/{t.id}", status_code=303)


@router.get("/transfers", response_class=HTMLResponse)
async def history(request: Request, session: AsyncSession = Depends(get_session)):
    s = request.session
    items = await transfers.by_wallet(session, s.get("solana"), s.get("aptos"))
    return templates.TemplateResponse(request, "transfers.html", _ctx(request, items=items))
