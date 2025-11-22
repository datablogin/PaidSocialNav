"""Meta (Facebook/Instagram/WhatsApp) platform adapter."""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import date as _date
from typing import Any

import requests

from ..base import BaseAdapter, InsightRecord
from ...core.enums import Entity, DatePreset
from ...core.models import DateRange


class MetaAdapter(BaseAdapter):
    """Adapter for Meta Business API (Facebook, Instagram, WhatsApp ads)."""

    BASE_URL = "https://graph.facebook.com/v18.0"

    def __init__(self, access_token: str, timeout: int = 60):
        """Initialize Meta adapter with access token and optional timeout.

        Args:
            access_token: Meta API access token
            timeout: Request timeout in seconds (default: 60)
        """
        super().__init__(access_token)
        self.timeout = timeout

    def _sanitize_error(self, error_data: dict[str, Any] | str) -> dict[str, Any] | str:
        """Recursively remove sensitive data from error responses to prevent token leakage.

        Args:
            error_data: Error response from API (dict or string)

        Returns:
            Sanitized error data with tokens redacted
        """
        if isinstance(error_data, dict):
            sanitized = {}
            sensitive_keys = {"access_token", "token", "authorization", "api_key", "secret"}

            for key, value in error_data.items():
                # Check if key itself is sensitive
                if key.lower() in sensitive_keys:
                    sanitized[key] = "***REDACTED***"
                # Recursively sanitize nested dicts
                elif isinstance(value, dict):
                    sanitized[key] = self._sanitize_error(value)
                # Check if string values contain sensitive patterns
                elif isinstance(value, str):
                    # Check for common token patterns in the value
                    if any(pattern in value.lower() for pattern in sensitive_keys):
                        sanitized[key] = "***CONTAINS_SENSITIVE_DATA***"
                    # Also check for OAuth token patterns (EAA, ya29, etc.)
                    elif any(value.startswith(prefix) for prefix in ["EAA", "ya29.", "sk-", "ghp_"]):
                        sanitized[key] = "***REDACTED***"
                    else:
                        sanitized[key] = value[:500]  # Limit string length
                else:
                    sanitized[key] = value
            return sanitized
        # For string errors, limit length to prevent accidental token exposure
        return str(error_data)[:500] if error_data else ""

    def fetch_insights(
        self,
        *,
        level: Entity,
        account_id: str,
        date_range: DateRange | None,
        date_preset: DatePreset | None = None,
        page_size: int = 500,
    ) -> Iterable[InsightRecord]:
        """Fetch insights from Meta Graph API.

        See BaseAdapter.fetch_insights for full documentation.
        """

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
            resp = requests.get(url, params=params, timeout=self.timeout)
            if resp.status_code != 200:
                try:
                    err_json = resp.json()
                except Exception:
                    err_json = {"error": resp.text[:200]}  # Limit error text length
                raise RuntimeError(f"Meta insights API error: {self._sanitize_error(err_json)}")

            data = resp.json() or {}
            rows = data.get("data", []) or []
            for row in rows:
                ds = row.get("date_start")
                # Graph returns daily rows; use date_start
                try:
                    d = _date.fromisoformat(ds) if ds else None
                except Exception:
                    d = None

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
                    impressions=self._safe_int(row.get("impressions")),
                    clicks=self._safe_int(row.get("clicks")),
                    spend=float(row.get("spend") or 0.0),
                    conversions=conv,
                    ctr=self._safe_float(row.get("ctr")),
                    frequency=self._safe_float(row.get("frequency")),
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

    def fetch_account(self, account_id: str) -> dict[str, Any]:
        """Fetch account details from Meta Graph API.

        Args:
            account_id: Meta ad account ID (with or without act_ prefix)

        Returns:
            Dictionary containing account details

        Raises:
            RuntimeError: On API errors
        """
        fields = [
            "id",
            "account_id",
            "name",
            "currency",
            "timezone_name",
            "account_status",
        ]

        endpoint = f"{self.BASE_URL}/{account_id}"
        params: dict[str, str] = {
            "access_token": self.access_token,
            "fields": ",".join(fields),
        }

        resp = requests.get(endpoint, params=params, timeout=self.timeout)
        if resp.status_code != 200:
            try:
                err_json = resp.json()
            except Exception:
                err_json = {"error": resp.text[:200]}  # Limit error text length
            raise RuntimeError(f"Meta account API error: {self._sanitize_error(err_json)}")

        return resp.json() or {}

    def fetch_campaigns(
        self, account_id: str, page_size: int = 500
    ) -> Iterable[dict[str, Any]]:
        """Fetch campaigns from Meta Graph API.

        Args:
            account_id: Meta ad account ID (with or without act_ prefix)
            page_size: Number of records per page

        Yields:
            Campaign records

        Raises:
            RuntimeError: On API errors
        """
        fields = [
            "id",
            "name",
            "status",
            "objective",
            "buying_type",
            "daily_budget",
            "lifetime_budget",
            "created_time",
            "updated_time",
        ]

        endpoint = f"{self.BASE_URL}/{account_id}/campaigns"
        params: dict[str, str | int] = {
            "access_token": self.access_token,
            "fields": ",".join(fields),
            "limit": page_size,
        }

        url = endpoint
        while True:
            resp = requests.get(url, params=params, timeout=self.timeout)
            if resp.status_code != 200:
                try:
                    err_json = resp.json()
                except Exception:
                    err_json = {"error": resp.text[:200]}  # Limit error text length
                raise RuntimeError(f"Meta campaigns API error: {self._sanitize_error(err_json)}")

            data = resp.json() or {}
            rows = data.get("data", []) or []
            yield from rows

            # Pagination
            paging = data.get("paging") or {}
            next_url = paging.get("next")
            if next_url:
                url = next_url
                params = {}
                continue
            break

    def fetch_adsets(
        self, account_id: str, page_size: int = 500
    ) -> Iterable[dict[str, Any]]:
        """Fetch ad sets from Meta Graph API.

        Args:
            account_id: Meta ad account ID (with or without act_ prefix)
            page_size: Number of records per page

        Yields:
            Ad set records

        Raises:
            RuntimeError: On API errors
        """
        fields = [
            "id",
            "name",
            "status",
            "campaign_id",
            "optimization_goal",
            "billing_event",
            "bid_strategy",
            "daily_budget",
            "lifetime_budget",
            "start_time",
            "end_time",
            "created_time",
            "updated_time",
        ]

        endpoint = f"{self.BASE_URL}/{account_id}/adsets"
        params: dict[str, str | int] = {
            "access_token": self.access_token,
            "fields": ",".join(fields),
            "limit": page_size,
        }

        url = endpoint
        while True:
            resp = requests.get(url, params=params, timeout=self.timeout)
            if resp.status_code != 200:
                try:
                    err_json = resp.json()
                except Exception:
                    err_json = {"error": resp.text[:200]}  # Limit error text length
                raise RuntimeError(f"Meta adsets API error: {self._sanitize_error(err_json)}")

            data = resp.json() or {}
            rows = data.get("data", []) or []
            yield from rows

            # Pagination
            paging = data.get("paging") or {}
            next_url = paging.get("next")
            if next_url:
                url = next_url
                params = {}
                continue
            break

    def fetch_ads(
        self, account_id: str, page_size: int = 500
    ) -> Iterable[dict[str, Any]]:
        """Fetch ads from Meta Graph API.

        Args:
            account_id: Meta ad account ID (with or without act_ prefix)
            page_size: Number of records per page

        Yields:
            Ad records

        Raises:
            RuntimeError: On API errors
        """
        fields = [
            "id",
            "name",
            "status",
            "adset_id",
            "campaign_id",
            "creative",
            "created_time",
            "updated_time",
        ]

        endpoint = f"{self.BASE_URL}/{account_id}/ads"
        params: dict[str, str | int] = {
            "access_token": self.access_token,
            "fields": ",".join(fields),
            "limit": page_size,
        }

        url = endpoint
        while True:
            resp = requests.get(url, params=params, timeout=self.timeout)
            if resp.status_code != 200:
                try:
                    err_json = resp.json()
                except Exception:
                    err_json = {"error": resp.text[:200]}  # Limit error text length
                raise RuntimeError(f"Meta ads API error: {self._sanitize_error(err_json)}")

            data = resp.json() or {}
            rows = data.get("data", []) or []
            yield from rows

            # Pagination
            paging = data.get("paging") or {}
            next_url = paging.get("next")
            if next_url:
                url = next_url
                params = {}
                continue
            break

    def fetch_creatives(
        self, account_id: str, page_size: int = 500
    ) -> Iterable[dict[str, Any]]:
        """Fetch ad creatives from Meta Graph API.

        Args:
            account_id: Meta ad account ID (with or without act_ prefix)
            page_size: Number of records per page

        Yields:
            Creative records

        Raises:
            RuntimeError: On API errors
        """
        fields = [
            "id",
            "name",
            "status",
            "title",
            "body",
            "call_to_action_type",
            "image_url",
            "video_id",
            "thumbnail_url",
            "object_story_spec",
        ]

        endpoint = f"{self.BASE_URL}/{account_id}/adcreatives"
        params: dict[str, str | int] = {
            "access_token": self.access_token,
            "fields": ",".join(fields),
            "limit": page_size,
        }

        url = endpoint
        while True:
            resp = requests.get(url, params=params, timeout=self.timeout)
            if resp.status_code != 200:
                try:
                    err_json = resp.json()
                except Exception:
                    err_json = {"error": resp.text[:200]}  # Limit error text length
                raise RuntimeError(f"Meta creatives API error: {self._sanitize_error(err_json)}")

            data = resp.json() or {}
            rows = data.get("data", []) or []
            yield from rows

            # Pagination
            paging = data.get("paging") or {}
            next_url = paging.get("next")
            if next_url:
                url = next_url
                params = {}
                continue
            break
