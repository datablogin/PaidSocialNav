from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Settings:
    gcp_project_id: str | None
    bq_dataset: str | None
    meta_access_token: str | None


def _read_env_file() -> dict[str, str]:
    """Load minimal .env to support PSN_* keys if not in the environment.

    We intentionally do not overwrite existing os.environ values.
    """
    env_path = Path.cwd() / ".env"
    env: dict[str, str] = {}
    if not env_path.exists():
        return env
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            env[k] = v
    except Exception:
        # Silently ignore .env parse failures to avoid breaking CLI usage
        return {}
    return env


def _get_env(
    name: str,
    fallback_names: list[str] | None = None,
    env_file: dict[str, str] | None = None,
) -> str | None:
    # Priority: process env -> .env -> fallback names
    val = os.getenv(name)
    if val:
        return val
    if env_file and name in env_file:
        return env_file[name]
    if fallback_names:
        for fb in fallback_names:
            v = os.getenv(fb)
            if v:
                return v
            if env_file and fb in env_file:
                return env_file[fb]
    return None


def get_settings() -> Settings:
    env_file = _read_env_file()
    # Support PSN_* prefixed variables with non-prefixed fallbacks
    gcp = _get_env("PSN_GCP_PROJECT_ID", ["GCP_PROJECT_ID"], env_file)
    bq = _get_env("PSN_BQ_DATASET", ["BQ_DATASET"], env_file)
    token = _get_env("PSN_META_ACCESS_TOKEN", ["META_ACCESS_TOKEN"], env_file)
    return Settings(
        gcp_project_id=gcp,
        bq_dataset=bq,
        meta_access_token=token,
    )
