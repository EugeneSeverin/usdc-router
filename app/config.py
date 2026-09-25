from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./usdc_router.db"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = "dev-only-change-me"
    base_url: str = "http://localhost:8000"
    network_mode: str = "mainnet"  # mainnet | testnet
    telegram_token: str = ""
    collect_interval_seconds: int = 300
    service_fee_bps: int = 10  # 0.1%
    min_transfer_usdc: float = 10.0
    solana_rpc_urls: str = "https://api.mainnet-beta.solana.com"  # через запятую: основной, резервный
    aptos_rpc_urls: str = "https://api.mainnet.aptoslabs.com/v1"
    defillama_yields_url: str = "https://yields.llama.fi"
    discrepancy_pp: float = 1.0  # п.4.1: расхождение источников
    discrepancy_minutes: int = 30

    @property
    def solana_rpcs(self) -> list[str]:
        return [u.strip() for u in self.solana_rpc_urls.split(",") if u.strip()]

    @property
    def aptos_rpcs(self) -> list[str]:
        return [u.strip() for u in self.aptos_rpc_urls.split(",") if u.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


def _load_yaml(name: str) -> dict[str, Any]:
    return yaml.safe_load((ROOT / "config" / name).read_text(encoding="utf-8"))


@lru_cache
def protocols_config() -> list[dict[str, Any]]:
    return _load_yaml("protocols.yaml")["protocols"]


@lru_cache
def cctp_config() -> dict[str, Any]:
    return _load_yaml("cctp.yaml")
