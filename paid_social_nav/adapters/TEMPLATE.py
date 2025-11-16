"""Template for implementing new platform adapters.

To add a new platform (e.g., Reddit, Pinterest, TikTok, X):

1. Copy this file to adapters/{platform}/adapter.py
2. Rename class to {Platform}Adapter
3. Set BASE_URL to platform's API endpoint
4. Implement fetch_insights() method following the contract
5. Add platform to Platform enum in core/enums.py
6. Update sync layer to support new platform
7. Add integration tests

Example for Reddit:
    from ..base import BaseAdapter, InsightRecord

    class RedditAdapter(BaseAdapter):
        BASE_URL = "https://ads-api.reddit.com/api/v2.0"

        def fetch_insights(self, *, level, account_id, date_range, date_preset, page_size):
            # Implement Reddit-specific API calls
            # Parse response into InsightRecord objects
            # Use yield for each record
"""

from collections.abc import Iterable

from .base import BaseAdapter, InsightRecord
from ..core.enums import Entity, DatePreset
from ..core.models import DateRange


class PlatformAdapter(BaseAdapter):
    """TODO: Rename to YourPlatformAdapter (e.g., RedditAdapter)."""

    BASE_URL = "TODO: Set platform API endpoint"

    def fetch_insights(
        self,
        *,
        level: Entity,
        account_id: str,
        date_range: DateRange | None,
        date_preset: DatePreset | None = None,
        page_size: int = 500,
    ) -> Iterable[InsightRecord]:
        """Fetch insights from platform API.

        TODO: Implement platform-specific logic:
        1. Construct API request with platform-specific parameters
        2. Handle authentication (self.access_token)
        3. Implement pagination loop
        4. Parse platform response into InsightRecord format
        5. Use yield to return records incrementally
        6. Raise RuntimeError on API errors
        """
        raise NotImplementedError(
            "Subclass must implement fetch_insights() method"
        )
