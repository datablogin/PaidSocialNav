"""Tests for dimension sync functionality."""

from unittest.mock import MagicMock, patch


from paid_social_nav.adapters.meta.dimensions import (
    _norm_act,
    _parse_timestamp,
    _safe_float,
    sync_account_dimension,
    sync_campaign_dimensions,
)


class TestHelperFunctions:
    """Test helper functions."""

    def test_norm_act_with_prefix(self) -> None:
        """Test account ID normalization with act_ prefix."""
        assert _norm_act("act_123456789") == "act_123456789"

    def test_norm_act_without_prefix(self) -> None:
        """Test account ID normalization without act_ prefix."""
        assert _norm_act("123456789") == "act_123456789"

    def test_parse_timestamp_valid(self) -> None:
        """Test timestamp parsing with valid input."""
        result = _parse_timestamp("2024-01-15T10:30:00Z")
        assert result is not None
        assert "2024-01-15" in result

    def test_parse_timestamp_none(self) -> None:
        """Test timestamp parsing with None."""
        assert _parse_timestamp(None) is None

    def test_parse_timestamp_invalid(self) -> None:
        """Test timestamp parsing with invalid input."""
        assert _parse_timestamp("invalid") is None

    def test_safe_float_valid(self) -> None:
        """Test safe float conversion with valid input."""
        assert _safe_float("123.45") == 123.45
        assert _safe_float(100) == 100.0

    def test_safe_float_none(self) -> None:
        """Test safe float conversion with None."""
        assert _safe_float(None) is None

    def test_safe_float_invalid(self) -> None:
        """Test safe float conversion with invalid input."""
        assert _safe_float("invalid") is None


class TestDimensionSync:
    """Test dimension sync functions."""

    @patch("paid_social_nav.adapters.meta.dimensions.ensure_dim_account_table")
    @patch("paid_social_nav.adapters.meta.dimensions.upsert_dimension")
    def test_sync_account_dimension(
        self, mock_upsert: MagicMock, mock_ensure_table: MagicMock
    ) -> None:
        """Test account dimension sync."""
        # Mock adapter
        mock_adapter = MagicMock()
        mock_adapter.fetch_account.return_value = {
            "id": "act_123456789",
            "account_id": "123456789",
            "name": "Test Account",
            "currency": "USD",
            "timezone_name": "America/Los_Angeles",
            "account_status": 1,
        }

        # Mock upsert to return 1 row
        mock_upsert.return_value = 1

        # Call sync
        count = sync_account_dimension(
            account_id="123456789",
            project_id="test-project",
            dataset="test_dataset",
            adapter=mock_adapter,
        )

        # Verify
        assert count == 1
        mock_adapter.fetch_account.assert_called_once_with("act_123456789")
        mock_ensure_table.assert_called_once_with("test-project", "test_dataset")
        mock_upsert.assert_called_once()

        # Check upsert call arguments
        call_args = mock_upsert.call_args
        assert call_args.kwargs["project_id"] == "test-project"
        assert call_args.kwargs["dataset"] == "test_dataset"
        assert call_args.kwargs["table_name"] == "dim_account"
        assert call_args.kwargs["merge_key"] == "account_global_id"
        assert len(call_args.kwargs["rows"]) == 1

        # Check row content
        row = call_args.kwargs["rows"][0]
        assert row["account_global_id"] == "meta:account:act_123456789"
        assert row["platform_account_id"] == "123456789"
        assert row["account_name"] == "Test Account"
        assert row["currency"] == "USD"
        assert row["timezone"] == "America/Los_Angeles"
        assert row["account_status"] == "1"

    @patch("paid_social_nav.adapters.meta.dimensions.ensure_dim_campaign_table")
    @patch("paid_social_nav.adapters.meta.dimensions.upsert_dimension")
    def test_sync_campaign_dimensions(
        self, mock_upsert: MagicMock, mock_ensure_table: MagicMock
    ) -> None:
        """Test campaign dimension sync."""
        # Mock adapter
        mock_adapter = MagicMock()
        mock_adapter.fetch_campaigns.return_value = [
            {
                "id": "123456",
                "name": "Test Campaign",
                "status": "ACTIVE",
                "objective": "CONVERSIONS",
                "buying_type": "AUCTION",
                "daily_budget": "5000",
                "lifetime_budget": None,
                "created_time": "2024-01-01T00:00:00Z",
                "updated_time": "2024-01-15T10:30:00Z",
            }
        ]

        # Mock upsert to return 1 row
        mock_upsert.return_value = 1

        # Call sync
        count = sync_campaign_dimensions(
            account_id="act_123456789",
            project_id="test-project",
            dataset="test_dataset",
            adapter=mock_adapter,
            page_size=500,
            retries=3,
            retry_backoff=2.0,
        )

        # Verify
        assert count == 1
        mock_adapter.fetch_campaigns.assert_called_once_with(
            "act_123456789", page_size=500
        )
        mock_ensure_table.assert_called_once_with("test-project", "test_dataset")
        mock_upsert.assert_called_once()

        # Check row content
        call_args = mock_upsert.call_args
        row = call_args.kwargs["rows"][0]
        assert row["campaign_global_id"] == "meta:campaign:123456"
        assert row["platform_campaign_id"] == "123456"
        assert row["account_global_id"] == "meta:account:act_123456789"
        assert row["campaign_name"] == "Test Campaign"
        assert row["campaign_status"] == "ACTIVE"
        assert row["objective"] == "CONVERSIONS"
        assert row["daily_budget"] == 5000.0
        assert row["lifetime_budget"] is None

    @patch("paid_social_nav.adapters.meta.dimensions.ensure_dim_campaign_table")
    @patch("paid_social_nav.adapters.meta.dimensions.upsert_dimension")
    def test_sync_campaign_dimensions_empty(
        self, mock_upsert: MagicMock, mock_ensure_table: MagicMock
    ) -> None:
        """Test campaign dimension sync with no campaigns."""
        # Mock adapter
        mock_adapter = MagicMock()
        mock_adapter.fetch_campaigns.return_value = []

        # Call sync
        count = sync_campaign_dimensions(
            account_id="act_123456789",
            project_id="test-project",
            dataset="test_dataset",
            adapter=mock_adapter,
        )

        # Verify
        assert count == 0
        mock_adapter.fetch_campaigns.assert_called_once()
        mock_ensure_table.assert_not_called()
        mock_upsert.assert_not_called()
