from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from .enums import Entity


@dataclass(frozen=True)
class Tenant:
    id: str
    project_id: str
    dataset: str
    default_level: Entity | None = None


def _load_yaml() -> dict:
    cfg_path = Path("configs/tenants.yaml")
    if not cfg_path.exists():
        return {}
    with cfg_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_tenant(tenant_id: str) -> Tenant | None:
    data = _load_yaml()
    tenants = data.get("tenants", {})
    cfg = tenants.get(tenant_id)
    if not cfg:
        return None
    lvl = cfg.get("default_level")
    default_level = Entity(lvl) if lvl else None
    return Tenant(
        id=tenant_id,
        project_id=cfg.get("project_id"),
        dataset=cfg.get("dataset"),
        default_level=default_level,
    )
