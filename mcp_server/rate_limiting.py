"""Rate limiting for MCP server."""
from collections import defaultdict
from datetime import datetime
from typing import Any


class RateLimiter:
    """
    Token bucket rate limiter.

    Limits requests per tenant to prevent abuse.
    """

    def __init__(self, requests_per_minute: int = 60) -> None:
        self.requests_per_minute = requests_per_minute
        self.buckets: dict[str, dict[str, Any]] = defaultdict(lambda: {
            "tokens": float(requests_per_minute),
            "last_update": datetime.now()
        })

    async def check_limit(self, tenant_id: str) -> tuple[bool, str]:
        """
        Check if request is within rate limit.

        Returns:
            (allowed, message) tuple
        """
        bucket = self.buckets[tenant_id]
        now = datetime.now()

        # Refill tokens based on time elapsed
        elapsed = (now - bucket["last_update"]).total_seconds()
        tokens_to_add = elapsed * (self.requests_per_minute / 60)
        bucket["tokens"] = min(
            self.requests_per_minute,
            bucket["tokens"] + tokens_to_add
        )
        bucket["last_update"] = now

        # Check if request allowed
        if bucket["tokens"] >= 1:
            bucket["tokens"] -= 1
            return True, ""
        else:
            retry_after = int((1 - bucket["tokens"]) * 60 / self.requests_per_minute)
            return False, f"Rate limit exceeded. Retry after {retry_after} seconds."


# Global rate limiter instance
rate_limiter = RateLimiter(requests_per_minute=60)
