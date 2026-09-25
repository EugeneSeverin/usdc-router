"""Подключение кошельков (п.5.1): Solana Pay-совместимый connect и Petra deeplink."""

import io
import time
from html import escape

import qrcode
import qrcode.image.svg
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic import BaseModel
from solders.pubkey import Pubkey

from app.config import get_settings
from app.services import petra

router = APIRouter()

# Эфемерные ключи dApp живут на сервере (не в cookie). TTL 15 минут.
# TODO прод: Redis (несколько воркеров).
_KEYS: dict[str, tuple[float, petra.DappKeys]] = {}
KEY_TTL = 900


def _put_keys(sid: str, k: petra.DappKeys) -> None:
    now = time.time()
    for s in [s for s, (t, _) in _KEYS.items() if now - t > KEY_TTL]:
        _KEYS.pop(s, None)
    _KEYS[sid] = (now, k)


def get_keys(sid: str) -> petra.DappKeys | None:
    v = _KEYS.get(sid)
    return v[1] if v and time.time() - v[0] <= KEY_TTL else None


def _sid(request: Request) -> str:
    import secrets

    if "sid" not in request.session:
        request.session["sid"] = secrets.token_urlsafe(16)
    return request.session["sid"]


class SolanaConnect(BaseModel):
    account: str


@router.get("/api/solana/connect")
async def solana_connect_meta():
    """Solana Pay transaction request, GET: название и иконка для кошелька."""
    return {"label": "USDC Router", "icon": f"{get_settings().base_url}/static/icon.svg"}


@router.post("/api/solana/connect")
async def solana_connect(body: SolanaConnect, request: Request):
    try:
        pk = Pubkey.from_string(body.account)
    except ValueError as e:
        raise HTTPException(422, "invalid solana address") from e
    _sid(request)
    request.session["solana"] = str(pk)
    return {"connected": True}


@router.get("/wallet/solana/qr.svg")
async def solana_qr(request: Request):
    _sid(request)
    link = f"solana:{get_settings().base_url}/api/solana/connect"
    return _qr(link)


def _qr(text: str) -> Response:
    img = qrcode.make(text, image_factory=qrcode.image.svg.SvgPathImage)
    buf = io.BytesIO()
    img.save(buf)
    return Response(buf.getvalue(), media_type="image/svg+xml")


@router.get("/wallet/aptos/connect")
async def aptos_connect(request: Request):
    sid = _sid(request)
    keys = petra.DappKeys.generate()
    _put_keys(sid, keys)
    base = get_settings().base_url
    link = petra.connect_link("USDC Router", base, f"{base}/wallet/aptos/callback", keys.public_hex)
    request.session["petra_link"] = link
    return RedirectResponse("/wallet", status_code=303)


@router.get("/wallet/aptos/qr.svg")
async def aptos_qr(request: Request):
    link = request.session.get("petra_link")
    if not link:
        raise HTTPException(404, "start /wallet/aptos/connect first")
    return _qr(link)


@router.get("/wallet/aptos/callback")
async def aptos_callback(
    request: Request,
    response: str = Query(...),
    data: str | None = None,
    address: str | None = None,
):
    """Адрес возврата Petra. Адрес кошелька берём из data (или query) и валидируем."""
    sid = _sid(request)
    if get_keys(sid) is None:
        raise HTTPException(400, "session expired, reconnect")
    try:
        r = petra.parse_connect_response(response, data)
    except petra.PetraError as e:
        raise HTTPException(400, str(e)) from e
    addr = r["address"] or address
    if not addr or not petra.APTOS_ADDR.match(addr):
        raise HTTPException(400, "aptos address missing in response")
    request.session["aptos"] = addr
    request.session["petra_pub"] = r["petra_public_hex"]
    return RedirectResponse("/wallet", status_code=303)


@router.get("/wallet", response_class=HTMLResponse)
async def wallet_page(request: Request):
    s = request.session
    sol, apt = s.get("solana"), s.get("aptos")
    return HTMLResponse(
        "<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'>"
        "<title>Wallets</title><body style='font:15px system-ui;max-width:640px;margin:16px auto;padding:0 16px'>"
        "<h1>Wallets</h1>"
        f"<h3>Solana: {escape(sol or 'not connected')}</h3>"
        + ("" if sol else "<p>Scan with Phantom / Solflare:</p><img src='/wallet/solana/qr.svg' width=220>")
        + f"<h3>Aptos: {escape(apt or 'not connected')}</h3>"
        + (
            ""
            if apt
            else "<p><a href='/wallet/aptos/connect'>Connect Petra</a>"
            + (" — scan with the phone:</p><img src='/wallet/aptos/qr.svg' width=220>" if s.get("petra_link") else "</p>")
        )
        + "<p><a href='/'>← dashboard</a></p>"
    )
