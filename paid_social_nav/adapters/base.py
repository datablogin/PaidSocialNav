"""Base adapter interface for social media platform integrations."""

from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from typing import Any

from ..core.enums import Entity, DatePreset
from ..core.models import DateRange


@dataclass
class InsightRecord:
    """Standardized insight record returned by all adapters.

    All adapters must return data in this format for compatibility
    with the sync and audit systems.
    """

    date: date
    level: Entity
    impressions: int
    clicks: int
    spend: float
    conversions: float | int | None
    ctr: float | None
    frequency: float | None
    raw: dict[str, Any] | None


class BaseAdapter(ABC):
    """Abstract base class for social media platform adapters.

    All platform adapters (Meta, Reddit, Pinterest, TikTok, X) must implement
    this interface to ensure compatibility with the sync orchestration layer.

    Attributes:
        BASE_URL: Platform-specific API endpoint (must be set by subclass)
        access_token: Authentication token for API requests
    """

    BASE_URL: str = ""  # Must be overridden by subclass

    def __init__(self, access_token: str):
        """Initialize adapter with authentication token.

        Args:
            access_token: Platform-specific access token or API key
        """
        self.access_token = access_token
        if not self.BASE_URL:
            raise NotImplementedError(
                f"{self.__class__.__name__} must define BASE_URL class attribute"
            )

    @abstractmethod
    def fetch_insights(
        self,
        *,
        level: Entity,
        account_id: str,
        date_range: DateRange | None,
        date_preset: DatePreset | None = None,
        page_size: int = 500,
    ) -> Iterable[InsightRecord]:
        """Fetch advertising insights from platform API.

        This method must be implemented by each platform adapter to fetch
        insights data and return it in the standardized InsightRecord format.

        Args:
            level: Hierarchy level (ACCOUNT, CAMPAIGN, ADSET, AD)
            account_id: Platform-specific account identifier
            date_range: Explicit date range (since/until) if provided
            date_preset: Platform-specific or standardized date preset if provided
            page_size: Number of records per API request (for pagination control)

        Returns:
            Iterable of InsightRecord objects (use generator/yield for memory efficiency)

        Raises:
            RuntimeError: On API errors (caller handles retries)

        Notes:
            - Exactly one of date_range or date_preset should be provided
            - Implementations should handle pagination internally
            - Use generator pattern (yield) for memory efficiency
            - Raise exceptions on API errors; don't implement retry logic here
        """
        pass

    def _safe_int(self, value: Any, default: int = 0) -> int:
        """Safely convert value to int, returning default on failure.

        Helper method for parsing API responses with potentially missing/malformed data.
        """
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _safe_float(self, value: Any, default: float | None = None) -> float | None:
        """Safely convert value to float, returning default on failure.

        Helper method for parsing API responses with potentially missing/malformed data.
        """
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
