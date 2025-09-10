from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any
from collections.abc import Iterable

from ...core.enums import DatePreset, Entity
from ...core.models import DateRange


@dataclass
class InsightRecord:
    date: date
    level: Entity
    impressions: int
    clicks: int
    spend: float
    conversions: float | int | None
    ctr: float | None
    frequency: float | None
    raw: dict[str, Any] | None


class MetaAdapter:
    def __init__(self, access_token: str):
        self.access_token = access_token

    def fetch_insights(
        self,
        *,
        level: Entity,
        account_id: str,
        date_range: DateRange | None,
        date_preset: DatePreset | None = None,
        page_size: int = 500,
    ) -> Iterable[InsightRecord]:
        """Yield InsightRecord objects.

        Note: This is a scaffold. In production, this should call the Meta Graph API.
        For Issue #20, tests stitch at CLI and do not require live API calls.
        """
        raise NotImplementedError(
            "MetaAdapter.fetch_insights is not implemented in this branch."
        )
