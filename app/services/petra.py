"""Petra mobile deeplinks (petra.app/docs/mobile-deeplinks): connect и signAndSubmit.

Схема: NaCl Box (X25519 + XSalsa20-Poly1305). Сервер держит только эфемерный ключ dApp;
ключей пользователя не видит. Формат ответа Petra на connect подтверждается прототипом
(п.7 ТЗ, неделя 1 этапа 2), поэтому разбор ответа осторожный и строго валидирующий.
"""

import base64
import json
import re
from dataclasses import dataclass
from urllib.parse import urlencode

from nacl.public import Box, PrivateKey, PublicKey
from nacl.utils import random as nacl_random

APTOS_ADDR = re.compile(r"^0x[0-9a-fA-F]{1,64}$")


class PetraError(Exception):
    pass


@dataclass(slots=True)
class DappKeys:
    private_hex: str
    public_hex: str

    @classmethod
    def generate(cls) -> "DappKeys":
        sk = PrivateKey.generate()
        return cls(bytes(sk).hex(), bytes(sk.public_key).hex())


def _b64(obj: dict) -> str:
    return base64.b64encode(json.dumps(obj, separators=(",", ":")).encode()).decode()


def connect_link(app_name: str, domain: str, redirect_link: str, dapp_public_hex: str) -> str:
    data = {
        "appInfo": {"name": app_name, "domain": domain},
        "redirectLink": redirect_link,
        "dappEncryptionPublicKey": dapp_public_hex,
    }
    return "petra://api/v1/connect?" + urlencode({"data": _b64(data)})


def parse_connect_response(response: str, data_b64: str | None) -> dict:
    """Возвращает {petra_public_hex, address?, public_key?}. Бросает PetraError при отказе/мусоре."""
    if response != "approved":
        raise PetraError("connection rejected")
    try:
        raw = json.loads(base64.b64decode(data_b64 or "", validate=True))
        petra_pub = raw["petraPublicEncryptedKey"]
        bytes.fromhex(petra_pub)
        if len(petra_pub) != 64:
            raise ValueError("bad key length")
    except (ValueError, KeyError, json.JSONDecodeError, TypeError) as e:
        raise PetraError(f"bad connect response: {e}") from e
    out = {"petra_public_hex": petra_pub, "address": raw.get("address"), "public_key": raw.get("publicKey")}
    if out["address"] is not None and not APTOS_ADDR.match(str(out["address"])):
        raise PetraError("bad aptos address")
    return out


def sign_and_submit_link(
    app_name: str,
    domain: str,
    redirect_link: str,
    keys: DappKeys,
    petra_public_hex: str,
    payload: dict,
    nonce: bytes | None = None,
) -> str:
    """Шифрует payload entry-функции общим секретом и собирает deeplink signAndSubmit."""
    nonce = nonce or nacl_random(Box.NONCE_SIZE)
    box = Box(PrivateKey(bytes.fromhex(keys.private_hex)), PublicKey(bytes.fromhex(petra_public_hex)))
    ct = box.encrypt(json.dumps(payload, separators=(",", ":")).encode(), nonce).ciphertext
    data = {
        "appInfo": {"name": app_name, "domain": domain},
        "payload": ct.hex(),
        "redirectLink": redirect_link,
        "dappEncryptionPublicKey": keys.public_hex,
        "nonce": nonce.hex(),
    }
    return "petra://api/v1/signAndSubmit?" + urlencode({"data": _b64(data)})
