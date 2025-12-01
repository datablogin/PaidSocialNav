"""Tests for MCP server rate limiting."""

import pytest
from datetime import datetime, timedelta
from mcp_server.rate_limiting import RateLimiter


@pytest.mark.asyncio
async def test_rate_limiter_allows_within_limit():
    """Test that requests within limit are allowed."""
    limiter = RateLimiter(requests_per_minute=60)

    # First request should be allowed
    allowed, message = await limiter.check_limit("tenant1")
    assert allowed is True
    assert message == ""


@pytest.mark.asyncio
async def test_rate_limiter_blocks_over_limit():
    """Test that requests over limit are blocked."""
    limiter = RateLimiter(requests_per_minute=5)

    # Use up all tokens
    for _ in range(5):
        allowed, _ = await limiter.check_limit("tenant1")
        assert allowed is True

    # Next request should be blocked
    allowed, message = await limiter.check_limit("tenant1")
    assert allowed is False
    assert "Rate limit exceeded" in message
    assert "Retry after" in message


@pytest.mark.asyncio
async def test_rate_limiter_refills_tokens():
    """Test that tokens refill over time."""
    limiter = RateLimiter(requests_per_minute=60)

    # Use up some tokens
    for _ in range(10):
        await limiter.check_limit("tenant1")

    # Wait for tokens to refill (simulate time passing)
    bucket = limiter.buckets["tenant1"]
    bucket["last_update"] = datetime.now() - timedelta(seconds=30)

    # Should be able to make more requests now
    allowed, message = await limiter.check_limit("tenant1")
    assert allowed is True
    assert message == ""


@pytest.mark.asyncio
async def test_rate_limiter_per_tenant():
    """Test that rate limits are per tenant."""
    limiter = RateLimiter(requests_per_minute=5)

    # Use up tenant1's limit
    for _ in range(5):
        await limiter.check_limit("tenant1")

    # Tenant1 should be blocked
    allowed, _ = await limiter.check_limit("tenant1")
    assert allowed is False

    # Tenant2 should still be allowed
    allowed, message = await limiter.check_limit("tenant2")
    assert allowed is True
    assert message == ""


@pytest.mark.asyncio
async def test_rate_limiter_token_bucket_max():
    """Test that token bucket doesn't exceed maximum."""
    limiter = RateLimiter(requests_per_minute=60)

    # Simulate long idle period
    bucket = limiter.buckets["tenant1"]
    bucket["last_update"] = datetime.now() - timedelta(hours=1)

    # Check limit to trigger refill
    await limiter.check_limit("tenant1")

    # Bucket should be at max (60), not more
    bucket = limiter.buckets["tenant1"]
    # After one request, should have 59 tokens left (max 60 - 1 used)
    assert bucket["tokens"] <= 60


@pytest.mark.asyncio
async def test_rate_limiter_configurable_limit():
    """Test that rate limit is configurable."""
    limiter_60 = RateLimiter(requests_per_minute=60)
    limiter_10 = RateLimiter(requests_per_minute=10)

    # 60 req/min limiter should allow 60 requests
    for _ in range(60):
        allowed, _ = await limiter_60.check_limit("tenant1")
        assert allowed is True

    # 10 req/min limiter should block after 10
    for _ in range(10):
        await limiter_10.check_limit("tenant2")

    allowed, _ = await limiter_10.check_limit("tenant2")
    assert allowed is False
