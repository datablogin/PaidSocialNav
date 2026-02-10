"""Tests for backfill orchestration with window slicing and retries."""

from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest

from paid_social_nav.core.backfill import (
    BackfillResult,
    SliceGranularity,
    SliceResult,
    _is_retryable_error,
    _make_retryable_call,
    run_backfill,
    slice_date_range,
)
from paid_social_nav.core.models import DateRange


class TestSliceDateRange:
    """Tests for date range slicing."""

    def test_daily_slicing_single_day(self):
        """Single day produces one slice."""
        dr = DateRange(since=date(2025, 1, 1), until=date(2025, 1, 1))
        slices = slice_date_range(dr, SliceGranularity.DAILY)
        assert len(slices) == 1
        assert slices[0].since == date(2025, 1, 1)
        assert slices[0].until == date(2025, 1, 1)

    def test_daily_slicing_one_week(self):
        """7 days produces 7 daily slices."""
        dr = DateRange(since=date(2025, 1, 1), until=date(2025, 1, 7))
        slices = slice_date_range(dr, SliceGranularity.DAILY)
        assert len(slices) == 7
        # Each slice is exactly one day
        for s in slices:
            assert s.since == s.until

    def test_daily_slicing_90_days(self):
        """90-day backfill produces 90 daily slices."""
        dr = DateRange(since=date(2025, 1, 1), until=date(2025, 3, 31))
        slices = slice_date_range(dr, SliceGranularity.DAILY)
        assert len(slices) == 90
        # Verify continuity: each slice starts the day after the previous ends
        for i in range(1, len(slices)):
            assert slices[i].since == slices[i - 1].until + timedelta(days=1)

    def test_weekly_slicing_one_week(self):
        """7 days with weekly granularity produces 1 slice."""
        dr = DateRange(since=date(2025, 1, 1), until=date(2025, 1, 7))
        slices = slice_date_range(dr, SliceGranularity.WEEKLY)
        assert len(slices) == 1
        assert slices[0].since == date(2025, 1, 1)
        assert slices[0].until == date(2025, 1, 7)

    def test_weekly_slicing_90_days(self):
        """90-day window with weekly slicing produces ~13 slices."""
        dr = DateRange(since=date(2025, 1, 1), until=date(2025, 3, 31))
        slices = slice_date_range(dr, SliceGranularity.WEEKLY)
        assert len(slices) == 13  # 90/7 = 12.86, rounds up to 13
        # First slice starts on the first day
        assert slices[0].since == date(2025, 1, 1)
        # Last slice ends on the last day
        assert slices[-1].until == date(2025, 3, 31)

    def test_weekly_slicing_partial_last_week(self):
        """10-day range with weekly slicing has a partial last slice."""
        dr = DateRange(since=date(2025, 1, 1), until=date(2025, 1, 10))
        slices = slice_date_range(dr, SliceGranularity.WEEKLY)
        assert len(slices) == 2
        # First slice: 7 days
        assert slices[0].since == date(2025, 1, 1)
        assert slices[0].until == date(2025, 1, 7)
        # Second slice: remaining 3 days
        assert slices[1].since == date(2025, 1, 8)
        assert slices[1].until == date(2025, 1, 10)

    def test_invalid_date_range_raises(self):
        """Since after until raises ValueError."""
        dr = DateRange(since=date(2025, 3, 1), until=date(2025, 1, 1))
        with pytest.raises(ValueError, match="Invalid date range"):
            slice_date_range(dr, SliceGranularity.DAILY)

    def test_slices_cover_full_range(self):
        """Verify that slices cover every day in the range without gaps or overlaps."""
        dr = DateRange(since=date(2025, 1, 1), until=date(2025, 4, 30))
        for granularity in [SliceGranularity.DAILY, SliceGranularity.WEEKLY]:
            slices = slice_date_range(dr, granularity)
            assert slices[0].since == dr.since
            assert slices[-1].until == dr.until
            # No gaps between slices
            for i in range(1, len(slices)):
                assert slices[i].since == slices[i - 1].until + timedelta(days=1)


class TestRetryableErrorDetection:
    """Tests for _is_retryable_error helper."""

    def test_rate_limit_message(self):
        assert _is_retryable_error(RuntimeError("Rate limit exceeded"))

    def test_too_many_calls(self):
        assert _is_retryable_error(RuntimeError("Too many calls to API"))

    def test_http_429(self):
        assert _is_retryable_error(RuntimeError("HTTP 429 Too Many Requests"))

    def test_http_500(self):
        assert _is_retryable_error(RuntimeError("HTTP 500 Internal Server Error"))

    def test_http_502(self):
        assert _is_retryable_error(RuntimeError("502 Bad Gateway"))

    def test_http_503(self):
        assert _is_retryable_error(RuntimeError("503 Service Unavailable"))

    def test_meta_error_code_32(self):
        assert _is_retryable_error(
            RuntimeError("Meta error: {'code': 32, 'message': 'rate limited'}")
        )

    def test_non_retryable_error(self):
        assert not _is_retryable_error(RuntimeError("Invalid credentials"))

    def test_non_retryable_value_error(self):
        assert not _is_retryable_error(ValueError("Bad date format"))

    def test_no_false_positive_on_embedded_500(self):
        """Ensure '500' inside a larger number does not trigger a match."""
        assert not _is_retryable_error(RuntimeError("loaded 5002 rows"))

    def test_no_false_positive_on_account_id(self):
        """Ensure '502' inside an account ID does not trigger a match."""
        assert not _is_retryable_error(RuntimeError("account ID 50032"))


class TestMakeRetryableCall:
    """Tests for _make_retryable_call with tenacity retry logic."""

    def test_success_on_first_attempt(self):
        """Function succeeds immediately, no retries needed."""
        func = MagicMock(return_value=42)
        rows, attempts = _make_retryable_call(func, max_attempts=3)
        assert rows == 42
        assert attempts == 1
        func.assert_called_once()

    def test_retry_on_rate_limit_then_succeed(self):
        """Retries on rate limit error, then succeeds."""
        call_count = 0

        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("Rate limit exceeded")
            return 10

        rows, attempts = _make_retryable_call(
            flaky, max_attempts=5, min_wait=0.01, max_wait=0.02
        )
        assert rows == 10
        assert attempts == 3

    def test_non_retryable_error_propagates_immediately(self):
        """Non-retryable errors are raised immediately without retry."""
        func = MagicMock(side_effect=ValueError("Invalid input"))
        with pytest.raises(ValueError, match="Invalid input"):
            _make_retryable_call(func, max_attempts=3)
        func.assert_called_once()

    def test_all_retries_exhausted(self):
        """Raises original error when all retries are exhausted."""
        func = MagicMock(side_effect=RuntimeError("Rate limit exceeded"))
        with pytest.raises(RuntimeError, match="Rate limit exceeded"):
            _make_retryable_call(
                func, max_attempts=3, min_wait=0.01, max_wait=0.02
            )
        assert func.call_count == 3

    def test_non_retryable_error_reports_single_attempt(self):
        """A non-retryable error on attempt 1 should report attempts=1."""
        func = MagicMock(side_effect=ValueError("Bad data"))
        with pytest.raises(ValueError) as exc_info:
            _make_retryable_call(func, max_attempts=5)
        # The exception should NOT claim 5 attempts were made
        assert getattr(exc_info.value, "attempts", None) == 1


class TestRunBackfill:
    """Tests for the main run_backfill orchestrator."""

    def test_successful_backfill(self):
        """All slices succeed."""
        dr = DateRange(since=date(2025, 1, 1), until=date(2025, 1, 3))
        fetch_and_load = MagicMock(return_value=10)

        result = run_backfill(
            date_range=dr,
            fetch_and_load=fetch_and_load,
            granularity=SliceGranularity.DAILY,
            max_retries=3,
            min_backoff=0.01,
            max_backoff=0.02,
        )

        assert result.total_rows == 30
        assert result.total_slices == 3
        assert result.successful_slices == 3
        assert result.failed_slices == 0
        assert result.success
        assert len(result.slice_results) == 3
        assert all(s.success for s in result.slice_results)
        assert fetch_and_load.call_count == 3

    def test_backfill_with_empty_slices(self):
        """Some slices return zero rows (no data for that day)."""
        dr = DateRange(since=date(2025, 1, 1), until=date(2025, 1, 3))
        # First day has data, second doesn't, third does
        fetch_and_load = MagicMock(side_effect=[5, 0, 3])

        result = run_backfill(
            date_range=dr,
            fetch_and_load=fetch_and_load,
            granularity=SliceGranularity.DAILY,
            max_retries=3,
            min_backoff=0.01,
            max_backoff=0.02,
        )

        assert result.total_rows == 8
        assert result.successful_slices == 3
        assert result.failed_slices == 0

    def test_backfill_stops_on_error_by_default(self):
        """Default behavior: stops on first unrecoverable failure."""
        dr = DateRange(since=date(2025, 1, 1), until=date(2025, 1, 3))
        # Second slice always fails with non-retryable error
        fetch_and_load = MagicMock(
            side_effect=[10, ValueError("Bad data"), 10]
        )

        with pytest.raises(ValueError, match="Bad data"):
            run_backfill(
                date_range=dr,
                fetch_and_load=fetch_and_load,
                granularity=SliceGranularity.DAILY,
                max_retries=3,
                min_backoff=0.01,
                max_backoff=0.02,
            )

    def test_backfill_continue_on_error(self):
        """With continue_on_error=True, processes all slices despite failures."""
        dr = DateRange(since=date(2025, 1, 1), until=date(2025, 1, 3))
        # Second slice fails with non-retryable error
        fetch_and_load = MagicMock(
            side_effect=[10, ValueError("Bad data"), 15]
        )

        result = run_backfill(
            date_range=dr,
            fetch_and_load=fetch_and_load,
            granularity=SliceGranularity.DAILY,
            max_retries=3,
            min_backoff=0.01,
            max_backoff=0.02,
            continue_on_error=True,
        )

        assert result.total_rows == 25
        assert result.successful_slices == 2
        assert result.failed_slices == 1
        assert not result.success
        failed = [s for s in result.slice_results if not s.success]
        assert len(failed) == 1
        assert "Bad data" in failed[0].error

    def test_backfill_failed_slice_reports_actual_attempts(self):
        """A non-retryable error on attempt 1 should report attempts=1, not max_retries."""
        dr = DateRange(since=date(2025, 1, 1), until=date(2025, 1, 1))
        fetch_and_load = MagicMock(side_effect=ValueError("Bad data"))

        result = run_backfill(
            date_range=dr,
            fetch_and_load=fetch_and_load,
            granularity=SliceGranularity.DAILY,
            max_retries=5,
            min_backoff=0.01,
            max_backoff=0.02,
            continue_on_error=True,
        )

        assert result.failed_slices == 1
        failed = result.slice_results[0]
        assert not failed.success
        assert failed.attempts == 1  # NOT 5

    def test_backfill_retries_rate_limits(self):
        """Rate limit errors are retried with backoff."""
        dr = DateRange(since=date(2025, 1, 1), until=date(2025, 1, 1))
        call_count = 0

        def flaky_fetch(window):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("Rate limit exceeded")
            return 5

        result = run_backfill(
            date_range=dr,
            fetch_and_load=flaky_fetch,
            granularity=SliceGranularity.DAILY,
            max_retries=5,
            min_backoff=0.01,
            max_backoff=0.02,
        )

        assert result.total_rows == 5
        assert result.successful_slices == 1
        assert result.slice_results[0].attempts == 3

    def test_backfill_weekly_granularity(self):
        """Weekly slicing works for a 14-day range."""
        dr = DateRange(since=date(2025, 1, 1), until=date(2025, 1, 14))
        fetch_and_load = MagicMock(return_value=50)

        result = run_backfill(
            date_range=dr,
            fetch_and_load=fetch_and_load,
            granularity=SliceGranularity.WEEKLY,
            max_retries=3,
            min_backoff=0.01,
            max_backoff=0.02,
        )

        assert result.total_slices == 2
        assert result.total_rows == 100

    def test_backfill_90_day_window(self):
        """90-day backfill creates 90 daily slices."""
        start = date(2025, 1, 1)
        end = start + timedelta(days=89)
        dr = DateRange(since=start, until=end)
        fetch_and_load = MagicMock(return_value=5)

        result = run_backfill(
            date_range=dr,
            fetch_and_load=fetch_and_load,
            granularity=SliceGranularity.DAILY,
            max_retries=3,
            min_backoff=0.01,
            max_backoff=0.02,
        )

        assert result.total_slices == 90
        assert result.total_rows == 450
        assert result.successful_slices == 90

    def test_backfill_result_summary(self):
        """BackfillResult.summary() returns correct dict."""
        result = BackfillResult(
            total_rows=100,
            total_slices=10,
            successful_slices=9,
            failed_slices=1,
            elapsed_seconds=45.678,
        )
        summary = result.summary()
        assert summary["total_rows"] == 100
        assert summary["total_slices"] == 10
        assert summary["successful_slices"] == 9
        assert summary["failed_slices"] == 1
        assert summary["elapsed_seconds"] == 45.68

    def test_backfill_progress_logging(self, caplog):
        """Verify progress logging during backfill."""
        import logging

        dr = DateRange(since=date(2025, 1, 1), until=date(2025, 1, 3))
        fetch_and_load = MagicMock(return_value=10)

        with caplog.at_level(logging.INFO):
            run_backfill(
                date_range=dr,
                fetch_and_load=fetch_and_load,
                granularity=SliceGranularity.DAILY,
                max_retries=3,
                min_backoff=0.01,
                max_backoff=0.02,
            )

        log_text = caplog.text
        assert "[1/3]" in log_text
        assert "[2/3]" in log_text
        assert "[3/3]" in log_text
        assert "Backfill complete" in log_text


class TestSliceResult:
    """Tests for SliceResult dataclass."""

    def test_successful_slice_result(self):
        dr = DateRange(since=date(2025, 1, 1), until=date(2025, 1, 1))
        sr = SliceResult(
            date_range=dr, rows_loaded=10, attempts=1, success=True
        )
        assert sr.success
        assert sr.error is None

    def test_failed_slice_result(self):
        dr = DateRange(since=date(2025, 1, 1), until=date(2025, 1, 1))
        sr = SliceResult(
            date_range=dr,
            rows_loaded=0,
            attempts=5,
            success=False,
            error="Rate limit exceeded",
        )
        assert not sr.success
        assert sr.error == "Rate limit exceeded"


class TestBackfillResult:
    """Tests for BackfillResult dataclass."""

    def test_success_property(self):
        result = BackfillResult(
            total_slices=3, successful_slices=3, failed_slices=0
        )
        assert result.success

    def test_failure_property(self):
        result = BackfillResult(
            total_slices=3, successful_slices=2, failed_slices=1
        )
        assert not result.success

    def test_empty_result_not_success(self):
        result = BackfillResult(total_slices=0)
        assert not result.success


class TestMakeRetryableCallEdgeCases:
    """Edge-case tests for _make_retryable_call."""

    def test_func_returning_zero_succeeds(self):
        """A function returning 0 (falsy int) should succeed, not be treated as failure."""
        func = MagicMock(return_value=0)
        rows, attempts = _make_retryable_call(func, max_attempts=3)
        assert rows == 0
        assert attempts == 1
        func.assert_called_once()


class TestBackfillMetaInsightsGranularityValidation:
    """Tests for granularity validation in backfill_meta_insights."""

    def test_invalid_granularity_raises_value_error(self):
        """backfill_meta_insights rejects unsupported granularity values."""
        from paid_social_nav.core.sync import backfill_meta_insights

        with pytest.raises(ValueError, match="Invalid granularity"):
            backfill_meta_insights(
                account_id="act_123",
                project_id="proj",
                dataset="ds",
                access_token="tok",
                since="2025-01-01",
                until="2025-01-07",
                granularity="monthly",
            )

    def test_valid_granularity_daily_accepted(self):
        """backfill_meta_insights accepts 'daily' granularity."""
        from unittest.mock import patch
        from paid_social_nav.core.sync import backfill_meta_insights
        from paid_social_nav.core.backfill import BackfillResult

        mock_result = BackfillResult(total_rows=5, total_slices=1, successful_slices=1)

        with patch("paid_social_nav.core.sync.MetaAdapter"),              patch("paid_social_nav.core.sync.ensure_dataset"),              patch("paid_social_nav.core.sync.ensure_insights_table"),              patch("paid_social_nav.core.sync.ensure_dim_ad_table"),              patch("paid_social_nav.core.sync.run_backfill", return_value=mock_result):
            result = backfill_meta_insights(
                account_id="act_123",
                project_id="proj",
                dataset="ds",
                access_token="tok",
                since="2025-01-01",
                until="2025-01-01",
                granularity="daily",
            )
            assert result["rows"] == 5

    def test_valid_granularity_weekly_accepted(self):
        """backfill_meta_insights accepts 'weekly' (case-insensitive)."""
        from unittest.mock import patch
        from paid_social_nav.core.sync import backfill_meta_insights
        from paid_social_nav.core.backfill import BackfillResult

        mock_result = BackfillResult(total_rows=10, total_slices=1, successful_slices=1)

        with patch("paid_social_nav.core.sync.MetaAdapter"),              patch("paid_social_nav.core.sync.ensure_dataset"),              patch("paid_social_nav.core.sync.ensure_insights_table"),              patch("paid_social_nav.core.sync.ensure_dim_ad_table"),              patch("paid_social_nav.core.sync.run_backfill", return_value=mock_result) as mock_bf:
            result = backfill_meta_insights(
                account_id="act_123",
                project_id="proj",
                dataset="ds",
                access_token="tok",
                since="2025-01-01",
                until="2025-01-14",
                granularity="Weekly",
            )
            assert result["rows"] == 10
            # Verify SliceGranularity.WEEKLY was passed to run_backfill
            call_kwargs = mock_bf.call_args[1]
            assert call_kwargs["granularity"] == SliceGranularity.WEEKLY
