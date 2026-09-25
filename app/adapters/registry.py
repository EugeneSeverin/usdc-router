from importlib import import_module

from app.adapters.base import ProtocolAdapter
from app.config import protocols_config


def load_adapter(cfg: dict) -> ProtocolAdapter:
    mod, cls = cfg["adapter"].split(":")
    return getattr(import_module(mod), cls)(cfg)


def load_adapters(only_active: bool = True) -> list[ProtocolAdapter]:
    return [load_adapter(c) for c in protocols_config() if c.get("is_active", True) or not only_active]
