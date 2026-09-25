import base64
import json
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import pytest_asyncio
import respx
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from nacl.public import Box, PrivateKey, PublicKey
from solders.keypair import Keypair
from starlette.middleware.sessions import SessionMiddleware

from app.api import transfers as transfers_api
from app.api import wallets
from app.core.security import SecurityHeadersMiddleware
from app.db import get_session
from app.models import Transfer, TransferStatus
from app.services import cctp, petra, solana_rpc
from app.services import transfers as svc

# ---------- Petra ----------


def _data(link: str) -> dict:
    q = parse_qs(urlparse(link).query)["data"][0]
    return json.loads(base64.b64decode(q))


def test_petra_connect_link_shape():
    keys = petra.DappKeys.generate()
    link = petra.connect_link("USDC Router", "https://x.io", "https://x.io/cb", keys.public_hex)
    assert link.startswith("petra://api/v1/connect?data=")
    d = _data(link)
    assert d["appInfo"] == {"name": "USDC Router", "domain": "https://x.io"}
    assert d["dappEncryptionPublicKey"] == keys.public_hex


def test_petra_sign_and_submit_wallet_can_decrypt():
    """Имитируем кошелёк: он должен расшифровать payload своим приватным ключом."""
    keys = petra.DappKeys.generate()
    petra_sk = PrivateKey.generate()
    payload = {"function": "0x1::coin::transfer", "arguments": ["0xabc", "1000000"]}
    link = petra.sign_and_submit_link(
        "app", "https://x.io", "https://x.io/cb", keys, bytes(petra_sk.public_key).hex(), payload
    )
    d = _data(link)
    box = Box(petra_sk, PublicKey(bytes.fromhex(d["dappEncryptionPublicKey"])))
    plain = box.decrypt(bytes.fromhex(d["payload"]), bytes.fromhex(d["nonce"]))
    assert json.loads(plain) == payload


def test_petra_response_validation():
    good = base64.b64encode(
        json.dumps({"petraPublicEncryptedKey": "ab" * 32, "address": "0x" + "1" * 64}).encode()
    ).decode()
    assert petra.parse_connect_response("approved", good)["address"] == "0x" + "1" * 64
    with pytest.raises(petra.PetraError):
        petra.parse_connect_response("rejected", good)
    with pytest.raises(petra.PetraError):
        petra.parse_connect_response("approved", "not-base64!!")
    bad_addr = base64.b64encode(
        json.dumps({"petraPublicEncryptedKey": "ab" * 32, "address": "<script>"}).encode()
    ).decode()
    with pytest.raises(petra.PetraError):
        petra.parse_connect_response("approved", bad_addr)


# ---------- CCTP / Iris ----------

IRIS = "https://iris.test"


@respx.mock
async def test_iris_attestation_ready_and_pending():
    c = cctp.IrisClient(base_url=IRIS)
    route = respx.get(f"{IRIS}/v2/messages/5")
    route.side_effect = [
        httpx.Response(404),
        httpx.Response(200, json={"messages": [{"status": "pending_confirmations", "attestation": "PENDING"}]}),
        httpx.Response(
            200,
            json={"messages": [{"status": "complete", "message": "0xaa", "attestation": "0xbb", "eventNonce": "7"}]},
        ),
    ]
    with pytest.raises(cctp.AttestationPending):
        await c.get_attestation("solana", "sig")
    with pytest.raises(cctp.AttestationPending):
        await c.get_attestation("solana", "sig")
    a = await c.get_attestation("solana", "sig")
    assert (a.message, a.attestation, a.nonce) == ("0xaa", "0xbb", "7")
    assert route.calls.last.request.url.params["transactionHash"] == "sig"


@respx.mock
async def test_iris_fee_and_errors():
    respx.get(f"{IRIS}/v2/burn/USDC/fees/5/9").respond(
        200, json=[{"finalityThreshold": 1000, "minimumFee": 1.3}, {"finalityThreshold": 2000, "minimumFee": 0}]
    )
    c = cctp.IrisClient(base_url=IRIS)
    assert await c.burn_fee_bps("solana", "aptos") == 1.3
    respx.get(f"{IRIS}/v2/messages/9").respond(500)
    with pytest.raises(cctp.CctpError):
        await c.get_attestation("aptos", "0xh")


def test_domains_match_circle_docs():
    assert cctp.domain("solana") == 5 and cctp.domain("aptos") == 9


# ---------- state machine ----------


def _t(status=TransferStatus.created):
    return Transfer(direction="solana_to_aptos", amount_usdc=100, status=status, fees={})


def test_transitions_forward_only():
    t = _t()
    for s in ["withdrawn", "burned", "attested", "minted", "deposited"]:
        svc.advance(t, TransferStatus(s))
    for bad in [TransferStatus.burned, TransferStatus.failed]:
        with pytest.raises(svc.TransferError):
            svc.advance(t, bad)


def test_cannot_fail_after_burn_funds_stay_recoverable():
    t = _t(TransferStatus.burned)
    with pytest.raises(svc.TransferError):
        svc.advance(t, TransferStatus.failed)
    assert svc.can_complete(t)


def test_fee_and_minimum():
    assert svc.service_fee(1000) == 1.0  # 0.1%
    with pytest.raises(svc.TransferError):
        svc.validate_amount(9.99)
    svc.validate_amount(10)


# ---------- Solana RPC (reference lookup + failover) ----------


@respx.mock
async def test_find_by_reference_and_failover(monkeypatch):
    monkeypatch.setenv("SOLANA_RPC_URLS", "https://a.test,https://b.test")
    from app import config

    config.get_settings.cache_clear()
    respx.post("https://a.test").respond(500)
    respx.post("https://b.test").respond(
        200, json={"jsonrpc": "2.0", "id": 1, "result": [{"signature": "bad", "err": {"x": 1}}, {"signature": "good", "err": None}]}
    )
    assert await solana_rpc.find_signature_by_reference("Ref") == "good"
    config.get_settings.cache_clear()


# ---------- API: wallets + transfers ----------


@pytest_asyncio.fixture
async def client(session):
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(SessionMiddleware, secret_key="test")
    app.include_router(wallets.router)
    app.include_router(transfers_api.router)

    async def _s():
        yield session

    app.dependency_overrides[get_session] = _s
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        yield c


async def test_solana_connect_validates_address(client):
    assert (await client.post("/api/solana/connect", json={"account": "nope"})).status_code == 422
    kp = str(Keypair().pubkey())
    r = await client.post("/api/solana/connect", json={"account": kp})
    assert r.json() == {"connected": True}
    assert kp in (await client.get("/wallet")).text


async def test_transfer_requires_both_wallets_and_min_amount(client):
    r = await client.post("/transfer", data={"direction": "solana_to_aptos", "amount": "100"})
    assert r.status_code == 400  # кошельки не подключены


async def test_transfer_flow_and_ownership(client, session):
    sol = str(Keypair().pubkey())
    await client.post("/api/solana/connect", json={"account": sol})
    # Aptos-адрес кладём через callback после генерации ключей
    await client.get("/wallet/aptos/connect")
    data = base64.b64encode(
        json.dumps({"petraPublicEncryptedKey": "ab" * 32, "address": "0x" + "2" * 64}).encode()
    ).decode()
    assert (await client.get("/wallet/aptos/callback", params={"response": "approved", "data": data})).status_code == 303

    assert (await client.post("/transfer", data={"direction": "solana_to_aptos", "amount": "5"})).status_code == 400
    r = await client.post("/transfer", data={"direction": "solana_to_aptos", "amount": "250"})
    assert r.status_code == 303
    page = await client.get(r.headers["location"])
    assert page.status_code == 200 and 'http-equiv="refresh"' in page.text

    t = await session.get(Transfer, 1)
    await svc.record_burn(session, t, "burnsig")
    page = await client.get("/transfer/1")
    assert "Завершить перевод" in page.text

    other = AsyncClient(transport=client._transport, base_url="http://t")  # другая сессия
    assert (await other.get("/transfer/1")).status_code == 404
    await other.aclose()


@respx.mock
async def test_complete_transfer_recovers_attestation(client, session, monkeypatch):
    sol = str(Keypair().pubkey())
    await client.post("/api/solana/connect", json={"account": sol})
    t = Transfer(direction="solana_to_aptos", amount_usdc=50, solana_address=sol, aptos_address="0x1",
                 status=TransferStatus.burned, burn_tx_hash="burnsig", fees={})
    session.add(t)
    await session.commit()
    respx.get(url__regex=r".*/v2/messages/5.*").respond(
        200, json={"messages": [{"status": "complete", "message": "0xaa", "attestation": "0xbb", "eventNonce": "1"}]}
    )
    r = await client.post(f"/transfer/{t.id}/complete")
    assert r.status_code == 303
    await session.refresh(t)
    assert t.status == TransferStatus.attested and t.cctp_attestation == "0xbb"
