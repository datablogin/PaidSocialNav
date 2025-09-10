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
    BASE_URL = "https://graph.facebook.com/v18.0"

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
        """Yield InsightRecord objects from Meta Graph API.

        - level: ad|adset|campaign
        - account_id: e.g., act_123 or numeric (but API expects act_123 style)
        - date_range: explicit since/until dates for daily breakdown when provided
        - date_preset: use Graph presets when provided (e.g., lifetime)
        - page_size: page size for API pagination
        """
        import json
        from datetime import date as _date
        import requests

        fields = [
            "date_start",
            "date_stop",
            "impressions",
            "clicks",
            "spend",
            "ctr",
            "frequency",
            "ad_id",
            "adset_id",
            "campaign_id",
            "actions",
        ]

        endpoint = f"{self.BASE_URL}/{account_id}/insights"
        params: dict[str, str | int] = {
            "access_token": self.access_token,
            "level": level.value,
            "fields": ",".join(fields),
            "time_increment": 1,  # daily
            "limit": page_size,
        }

        if date_preset is not None:
            params["date_preset"] = date_preset.value
        elif date_range is not None:
            params["time_range"] = json.dumps(
                {
                    "since": date_range.since.isoformat(),
                    "until": date_range.until.isoformat(),
                }
            )

        url = endpoint
        while True:
            resp = requests.get(url, params=params, timeout=60)
            if resp.status_code != 200:
                try:
                    err_json = resp.json()
                except Exception:
                    err_json = {"error": resp.text}
                raise RuntimeError(f"Meta insights API error: {err_json}")

            data = resp.json() or {}
            rows = data.get("data", []) or []
            for row in rows:
                ds = row.get("date_start")
                # Graph returns daily rows; use date_start
                try:
                    d = _date.fromisoformat(ds) if ds else None
                except Exception:
                    d = None

                def _int(x: Any) -> int:
                    try:
                        return int(x)
                    except Exception:
                        return 0

                def _float(x: Any) -> float | None:
                    try:
                        return float(x)
                    except Exception:
                        return None

                # Sum all actions as a coarse conversions proxy (may be refined per rule)
                actions = row.get("actions") or []
                conv: float | int | None = None
                try:
                    if isinstance(actions, list) and actions:
                        s = 0.0
                        for a in actions:
                            v = a.get("value")
                            try:
                                s += float(v)
                            except Exception:
                                pass
                        conv = s
                except Exception:
                    conv = None

                yield InsightRecord(
                    date=d or _date.today(),
                    level=level,
                    impressions=_int(row.get("impressions")),
                    clicks=_int(row.get("clicks")),
                    spend=float(row.get("spend") or 0.0),
                    conversions=conv,
                    ctr=_float(row.get("ctr")),
                    frequency=_float(row.get("frequency")),
                    raw=row,
                )

            # Pagination: follow next if present
            paging = data.get("paging") or {}
            next_url = paging.get("next")
            if next_url:
                url = next_url
                # after the first request, params should be cleared to avoid duplication when following next URLs
                params = {}
                continue
            break
