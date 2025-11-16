"""Tests for base adapter interface."""

import pytest
from paid_social_nav.adapters.base import BaseAdapter


def test_base_adapter_requires_base_url():
    """Test that BaseAdapter subclasses must define BASE_URL."""

    class InvalidAdapter(BaseAdapter):
        # No BASE_URL defined
        def fetch_insights(self, **kwargs):
            pass

    with pytest.raises(NotImplementedError, match="must define BASE_URL"):
        InvalidAdapter(access_token="test_token")


def test_base_adapter_requires_fetch_insights():
    """Test that BaseAdapter subclasses must implement fetch_insights."""

    # Test that abstract method prevents instantiation
    class MinimalAdapter(BaseAdapter):
        BASE_URL = "https://example.com/api"

    # This should fail because fetch_insights is not implemented
    with pytest.raises(TypeError, match="abstract method fetch_insights"):
        MinimalAdapter(access_token="test_token")


def test_safe_int_helper():
    """Test _safe_int conversion helper."""

    class TestAdapter(BaseAdapter):
        BASE_URL = "https://example.com/api"
        def fetch_insights(self, **kwargs):
            pass

    adapter = TestAdapter(access_token="test")

    assert adapter._safe_int("123") == 123
    assert adapter._safe_int(456) == 456
    assert adapter._safe_int("invalid") == 0
    assert adapter._safe_int(None) == 0
    assert adapter._safe_int("bad", default=99) == 99


def test_safe_float_helper():
    """Test _safe_float conversion helper."""

    class TestAdapter(BaseAdapter):
        BASE_URL = "https://example.com/api"
        def fetch_insights(self, **kwargs):
            pass

    adapter = TestAdapter(access_token="test")

    assert adapter._safe_float("1.23") == 1.23
    assert adapter._safe_float(4.56) == 4.56
    assert adapter._safe_float("invalid") is None
    assert adapter._safe_float(None) is None
    assert adapter._safe_float("bad", default=9.9) == 9.9
