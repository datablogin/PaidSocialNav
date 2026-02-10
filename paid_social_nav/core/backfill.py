"""Backfill orchestration with window slicing and retry logic.

Provides robust backfill functionality that slices large date ranges into
configurable daily or weekly chunks, processes them sequentially with
progress logging, and retries transient failures using tenacity with
exponential backoff and jitter.

Addresses: https://github.com/datablogin/PaidSocialNav/issues/7
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum
from typing import Any, Callable

from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from ..core.models import DateRange

logger = logging.getLogger(__name__)


class SliceGranularity(str, Enum):
    """Granularity for backfill window slicing."""

    DAILY = "daily"
    WEEKLY = "weekly"


@dataclass
class SliceResult:
    """Result of processing a single backfill slice."""

    date_range: DateRange
    rows_loaded: int
    attempts: int
    success: bool
    error: str | None = None
    elapsed_seconds: float = 0.0


@dataclass
class BackfillResult:
    """Aggregated result of a complete backfill operation."""

    total_rows: int = 0
    total_slices: int = 0
    successful_slices: int = 0
    failed_slices: int = 0
    slice_results: list[SliceResult] = field(default_factory=list)
    elapsed_seconds: float = 0.0

    @property
    def success(self) -> bool:
        """True if all slices succeeded."""
        return self.failed_slices == 0 and self.total_slices > 0

    def summary(self) -> dict[str, Any]:
        """Return a summary dict suitable for logging or CLI output."""
        return {
            "total_rows": self.total_rows,
            "total_slices": self.total_slices,
            "successful_slices": self.successful_slices,
            "failed_slices": self.failed_slices,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
        }


def slice_date_range(
    date_range: DateRange,
    granularity: SliceGranularity = SliceGranularity.DAILY,
) -> list[DateRange]:
    """Slice a date range into smaller chunks.

    Args:
        date_range: The full date range to slice.
        granularity: DAILY (1-day slices) or WEEKLY (7-day slices).

    Returns:
        List of DateRange objects covering the full period.
    """
    if date_range.since > date_range.until:
        raise ValueError(
            f"Invalid date range: since ({date_range.since}) is after "
            f"until ({date_range.until})"
        )

    step_days = 1 if granularity == SliceGranularity.DAILY else 7
    step = timedelta(days=step_days)

    slices: list[DateRange] = []
    cursor = date_range.since
    while cursor <= date_range.until:
        end = min(cursor + step - timedelta(days=1), date_range.until)
        slices.append(DateRange(since=cursor, until=end))
        cursor = end + timedelta(days=1)

    return slices


def _is_retryable_error(exc: BaseException) -> bool:
    """Check if an exception is retryable (rate limit or server error).

    Detects Meta API rate limit errors (code 32, subcode 2446079) and
    HTTP 429/5xx errors from RuntimeError messages.
    """
    msg = str(exc).lower()
    # Meta API rate limit indicators
    if "rate limit" in msg or "too many calls" in msg:
        return True
    # HTTP status code patterns — use word boundaries to avoid false positives
    # (e.g., "loaded 5002 rows" or "account ID 50032")
    if re.search(r'\b(429|500|502|503)\b', msg):
        return True
    # Meta error code 32 = rate limit
    if "'code': 32" in msg or '"code": 32' in msg:
        return True
    return False


class _RetryableError(Exception):
    """Wrapper to signal that an error is retryable."""

    pass


def _make_retryable_call(
    func: Callable[[], int],
    max_attempts: int = 5,
    min_wait: float = 1.0,
    max_wait: float = 60.0,
) -> tuple[int, int]:
    """Execute a function with tenacity retry on retryable errors.

    Args:
        func: Callable that returns row count (int).
        max_attempts: Maximum number of attempts.
        min_wait: Minimum wait time for exponential backoff (seconds).
        max_wait: Maximum wait time for exponential backoff (seconds).

    Returns:
        Tuple of (rows_loaded, attempts_used).

    Raises:
        The original exception if all retries are exhausted or the error
        is not retryable.  The exception will have an ``attempts``
        attribute attached with the actual number of attempts made.
    """
    # Mutable container so the inner function can communicate the attempt
    # count back to the caller even when an exception is raised.
    attempt_counter = [0]

    @retry(
        retry=retry_if_exception_type(_RetryableError),
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential_jitter(initial=min_wait, max=max_wait, jitter=2),
        reraise=True,
    )
    def _inner() -> int:
        attempt_counter[0] += 1
        try:
            return func()
        except Exception as e:
            if _is_retryable_error(e):
                logger.warning(
                    "Retryable error (attempt %d/%d): %s",
                    attempt_counter[0],
                    max_attempts,
                    e,
                )
                raise _RetryableError(str(e)) from e
            raise  # Non-retryable: propagate immediately

    def _attach_attempts(exc: BaseException) -> BaseException:
        """Attach the actual attempt count to the exception."""
        exc.attempts = attempt_counter[0]  # type: ignore[attr-defined]
        return exc

    try:
        rows = _inner()
        return rows, attempt_counter[0]
    except _RetryableError as e:
        # reraise=True causes tenacity to re-raise the _RetryableError
        # directly; unwrap to the original exception without setting
        # the _RetryableError as the cause (avoids confusing cause chain)
        if e.__cause__ is not None:
            raise _attach_attempts(e.__cause__)
        raise _attach_attempts(RuntimeError(str(e))) from e
    except RetryError as e:
        # Fallback: unwrap the original exception from tenacity
        raise _attach_attempts(e.last_attempt.exception()) from e
    except Exception as e:
        # Non-retryable errors: attach the attempt count so callers
        # can report the actual number of attempts made.
        raise _attach_attempts(e)


def run_backfill(
    date_range: DateRange,
    fetch_and_load: Callable[[DateRange], int],
    granularity: SliceGranularity = SliceGranularity.DAILY,
    max_retries: int = 5,
    min_backoff: float = 1.0,
    max_backoff: float = 60.0,
    continue_on_error: bool = False,
) -> BackfillResult:
    """Run a backfill operation with window slicing and retries.

    Slices the requested date range into daily or weekly chunks, processes
    each sequentially, and retries transient failures with exponential
    backoff and jitter.

    Args:
        date_range: Full date range to backfill.
        fetch_and_load: Callable that takes a DateRange and returns the
            number of rows loaded. This function should handle fetching
            from the adapter and loading to BigQuery.
        granularity: DAILY or WEEKLY slice granularity.
        max_retries: Maximum retry attempts per slice.
        min_backoff: Minimum backoff wait in seconds.
        max_backoff: Maximum backoff wait in seconds.
        continue_on_error: If True, continue processing remaining slices
            after a slice fails all retries. If False (default), stop on
            first unrecoverable failure.

    Returns:
        BackfillResult with aggregated metrics and per-slice details.

    Raises:
        Exception: Re-raises the last slice error if continue_on_error
            is False and a slice fails all retries.
    """
    slices = slice_date_range(date_range, granularity)
    total_slices = len(slices)

    logger.info(
        "Starting backfill: %d %s slices from %s to %s",
        total_slices,
        granularity.value,
        date_range.since.isoformat(),
        date_range.until.isoformat(),
    )

    result = BackfillResult(total_slices=total_slices)
    overall_start = time.monotonic()

    for idx, window in enumerate(slices, start=1):
        slice_start = time.monotonic()
        progress_prefix = f"[{idx}/{total_slices}]"

        logger.info(
            "%s Processing slice %s to %s",
            progress_prefix,
            window.since.isoformat(),
            window.until.isoformat(),
        )

        try:
            rows, attempts = _make_retryable_call(
                func=lambda w=window: fetch_and_load(w),
                max_attempts=max_retries,
                min_wait=min_backoff,
                max_wait=max_backoff,
            )
            elapsed = time.monotonic() - slice_start

            slice_result = SliceResult(
                date_range=window,
                rows_loaded=rows,
                attempts=attempts,
                success=True,
                elapsed_seconds=round(elapsed, 2),
            )
            result.total_rows += rows
            result.successful_slices += 1

            logger.info(
                "%s Slice complete: %d rows in %.1fs (attempt %d/%d)",
                progress_prefix,
                rows,
                elapsed,
                attempts,
                max_retries,
            )

        except Exception as e:
            elapsed = time.monotonic() - slice_start
            # Use the actual attempt count attached by _make_retryable_call,
            # falling back to max_retries if unavailable.
            actual_attempts = getattr(e, "attempts", max_retries)
            slice_result = SliceResult(
                date_range=window,
                rows_loaded=0,
                attempts=actual_attempts,
                success=False,
                error=str(e),
                elapsed_seconds=round(elapsed, 2),
            )
            result.failed_slices += 1

            logger.error(
                "%s Slice failed after %d attempts: %s",
                progress_prefix,
                actual_attempts,
                e,
            )

            result.slice_results.append(slice_result)

            if not continue_on_error:
                result.elapsed_seconds = round(
                    time.monotonic() - overall_start, 2
                )
                raise

            continue

        result.slice_results.append(slice_result)

    result.elapsed_seconds = round(time.monotonic() - overall_start, 2)

    logger.info(
        "Backfill complete: %d/%d slices succeeded, %d total rows in %.1fs",
        result.successful_slices,
        result.total_slices,
        result.total_rows,
        result.elapsed_seconds,
    )

    return result
