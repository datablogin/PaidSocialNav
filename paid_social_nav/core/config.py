from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class Settings:
    gcp_project_id: str | None
    bq_dataset: str | None
    meta_access_token: str | None


def get_settings() -> Settings:
    return Settings(
        gcp_project_id=os.getenv("GCP_PROJECT_ID"),
        bq_dataset=os.getenv("BQ_DATASET"),
        meta_access_token=os.getenv("META_ACCESS_TOKEN"),
    )
