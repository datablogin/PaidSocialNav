from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from time import sleep
from typing import Any
from collections.abc import Iterable

from ..adapters.meta.adapter import MetaAdapter
from ..core.backfill import (
    SliceGranularity,
    run_backfill,
)
from ..core.enums import DatePreset, Entity
from ..core.models import DateRange
from ..storage.bq import (
    INSIGHTS_TABLE,
    ensure_dataset,
    ensure_dim_ad_table,
    ensure_insights_table,
    load_json_rows,
)

logger = logging.getLogger(__name__)

FALLBACK_ORDER: list[Entity] = [Entity.AD, Entity.ADSET, Entity.CAMPAIGN]


def _norm_act(account_id: str) -> str:
    return account_id if account_id.startswith("act_") else f"act_{account_id}"


def _insight_record_to_bq_row(ir: Any, act: str) -> dict[str, Any]:
    """Convert an InsightRecord to a BigQuery row dict.

    This is the single source of truth for mapping adapter insight records
    to the BigQuery ``insights`` table schema, used by both
    ``sync_meta_insights`` and ``backfill_meta_insights``.
    """
    raw = ir.raw or {}
    ad_id = raw.get("ad_id")
    adset_id = raw.get("adset_id")
    campaign_id = raw.get("campaign_id")

    return {
        "date": ir.date.isoformat(),
        "level": ir.level.value,
        "account_global_id": f"meta:account:{act}",
        "campaign_global_id": f"meta:campaign:{campaign_id}"
        if campaign_id
        else None,
        "adset_global_id": f"meta:adset:{adset_id}"
        if adset_id
        else None,
        "ad_global_id": f"meta:ad:{ad_id}" if ad_id else None,
        "impressions": ir.impressions,
        "clicks": ir.clicks,
        "spend": ir.spend,
        "conversions": ir.conversions,
        "ctr": ir.ctr,
        "frequency": ir.frequency,
        "raw_metrics": raw,
    }


@dataclass(frozen=True)
class _ResolvedDates:
    date_range: DateRange | None
    date_preset: DatePreset | None


def _preset_to_range(
    preset: DatePreset, now: datetime | None = None
) -> tuple[date, date] | None:
    n = now or datetime.now(UTC)
    d = n.date()
    if preset is DatePreset.TODAY:
        return d, d
    if preset is DatePreset.YESTERDAY:
        y = d - timedelta(days=1)
        return y, y
    if preset is DatePreset.LAST_3D:
        return d - timedelta(days=3), d - timedelta(days=1)
    if preset is DatePreset.LAST_7D:
        return d - timedelta(days=7), d - timedelta(days=1)
    if preset is DatePreset.LAST_14D:
        return d - timedelta(days=14), d - timedelta(days=1)
    if preset is DatePreset.LAST_28D:
        return d - timedelta(days=28), d - timedelta(days=1)
    if preset is DatePreset.THIS_MONTH:
        return d.replace(day=1), d
    if preset is DatePreset.LAST_MONTH:
        first_this = d.replace(day=1)
        last_prev = first_this - timedelta(days=1)
        first_prev = last_prev.replace(day=1)
        return first_prev, last_prev
    if preset is DatePreset.LIFETIME:
        return None
    return None


def _resolve_dates(
    *,
    date_preset: DatePreset | None,
    since: str | None,
    until: str | None,
) -> _ResolvedDates:
    # If explicit dates exist, they take precedence; treat preset as None
    if since or until:
        if not (since and until):
            raise ValueError(
                "Both --since and --until must be provided if not using --date-preset"
            )
        dr = DateRange(since=date.fromisoformat(since), until=date.fromisoformat(until))
        return _ResolvedDates(date_range=dr, date_preset=None)
    if date_preset:
        rng = _preset_to_range(date_preset)
        if rng is None:
            # lifetime or adapter-native preset: pass preset through, no explicit range
            return _ResolvedDates(date_range=None, date_preset=date_preset)
        s, u = rng
        return _ResolvedDates(date_range=DateRange(since=s, until=u), date_preset=None)
    # Default to yesterday
    y = datetime.now(UTC).date() - timedelta(days=1)
    return _ResolvedDates(date_range=DateRange(since=y, until=y), date_preset=None)


def _chunks(dr: DateRange, *, chunk_days: int) -> Iterable[DateRange]:
    total_days = (dr.until - dr.since).days + 1
    if total_days <= 60:
        yield dr
        return
    step = timedelta(days=chunk_days)
    cursor = dr.since
    while cursor <= dr.until:
        end = min(cursor + step - timedelta(days=1), dr.until)
        yield DateRange(since=cursor, until=end)
        cursor = end + timedelta(days=1)


def sync_meta_insights(
    *,
    account_id: str,
    project_id: str,
    dataset: str,
    access_token: str,
    level: Entity = Entity.AD,
    levels: list[Entity] | None = None,
    fallback_levels: bool = True,
    date_preset: DatePreset | None = None,
    since: str | None = None,
    until: str | None = None,
    chunk_days: int = 30,
    retries: int = 3,
    retry_backoff: float = 2.0,
    rate_limit_rps: float = 0.0,
    page_size: int = 500,
) -> dict[str, Any]:
    """Fetch Meta insights (daily) and load to BigQuery with dedup."""
    act = _norm_act(account_id)
    resolved = _resolve_dates(date_preset=date_preset, since=since, until=until)

    adapter = MetaAdapter(access_token=access_token)

    # Ensure BQ dataset/table
    ensure_dataset(project_id, dataset)
    ensure_insights_table(project_id, dataset)
    ensure_dim_ad_table(project_id, dataset)

    def _fetch_and_load(run_level: Entity, dr: DateRange | None) -> int:
        rows: list[dict[str, Any]] = []
        loaded_count = 0
        # Prepare rate limiting
        min_interval = (
            1.0 / rate_limit_rps if rate_limit_rps and rate_limit_rps > 0 else 0.0
        )
        last_time: float | None = None

        def _maybe_sleep() -> None:
            nonlocal last_time
            if min_interval <= 0:
                return
            import time as _t

            now = _t.time()
            if last_time is None:
                last_time = now
                return
            elapsed = now - last_time
            if elapsed < min_interval:
                sleep(min_interval - elapsed)
            last_time = _t.time()

        # Determine date iterator
        if dr is not None:
            dr_iter = _chunks(dr, chunk_days=chunk_days)
            dp = None
        else:
            # preset-based (e.g., lifetime) – single logical chunk without explicit dates
            dr_iter = [None]
            dp = date_preset

        for chunk in dr_iter:
            attempt = 0
            while True:
                try:
                    _maybe_sleep()
                    for ir in adapter.fetch_insights(
                        level=run_level,
                        account_id=act,
                        date_range=chunk,
                        date_preset=dp,
                        page_size=page_size,
                    ):
                        rows.append(_insight_record_to_bq_row(ir, act))
                    # Load per chunk to keep memory bounded and enable dedup
                    if rows:
                        load_json_rows(
                            project_id=project_id,
                            dataset=dataset,
                            table=INSIGHTS_TABLE,
                            rows=rows,
                        )
                        loaded_count += len(rows)
                        rows.clear()
                    break
                except Exception as e:
                    attempt += 1
                    # Log error details before retry
                    error_msg = (
                        f"Chunk load failed (attempt {attempt}/{retries}): "
                        f"{type(e).__name__}: {str(e)}"
                    )
                    if attempt > retries:
                        print(f"ERROR: {error_msg} - Max retries exceeded", file=__import__('sys').stderr)
                        raise
                    # Exponential backoff
                    backoff_time = retry_backoff * (2 ** (attempt - 1))
                    print(
                        f"WARNING: {error_msg} - Retrying in {backoff_time:.1f}s",
                        file=__import__('sys').stderr
                    )
                    sleep(backoff_time)
        return loaded_count  # loading happens incrementally

    # Orchestrate levels

    if levels:
        total = 0
        for lv in levels:
            total += _fetch_and_load(lv, resolved.date_range)
        return {"rows": total, "table": f"{project_id}.{dataset}.{INSIGHTS_TABLE}"}

    # Single level with optional fallback
    tried_levels: list[Entity] = []
    current_level = level

    total = 0
    while True:
        tried_levels.append(current_level)
        rows_loaded = _fetch_and_load(current_level, resolved.date_range)
        total += rows_loaded

        # Stop if fallback disabled or we got data
        if not fallback_levels or rows_loaded > 0:
            break

        # If fallback is enabled, attempt next level only if not already tried all
        next_index = (
            FALLBACK_ORDER.index(current_level) + 1
            if current_level in FALLBACK_ORDER
            else len(FALLBACK_ORDER)
        )
        if next_index >= len(FALLBACK_ORDER):
            break
        current_level = FALLBACK_ORDER[next_index]

    return {"rows": total, "table": f"{project_id}.{dataset}.{INSIGHTS_TABLE}"}


def backfill_meta_insights(
    *,
    account_id: str,
    project_id: str,
    dataset: str,
    access_token: str,
    level: Entity = Entity.CAMPAIGN,
    since: str,
    until: str,
    granularity: str = "daily",
    max_retries: int = 5,
    min_backoff: float = 1.0,
    max_backoff: float = 60.0,
    continue_on_error: bool = False,
    page_size: int = 500,
) -> dict[str, Any]:
    """Backfill Meta insights over a large date range with window slicing and retries.

    Slices the requested period into daily or weekly chunks, processes each
    sequentially with progress logging, and retries transient failures
    (rate limits, server errors) using exponential backoff with jitter.

    Args:
        account_id: Meta ad account id (act_* or numeric).
        project_id: GCP project ID for BigQuery.
        dataset: BigQuery dataset name.
        access_token: Meta API access token.
        level: Insights hierarchy level (default: CAMPAIGN).
        since: Start date as YYYY-MM-DD string.
        until: End date as YYYY-MM-DD string.
        granularity: Slice granularity - "daily" or "weekly".
        max_retries: Maximum retry attempts per slice.
        min_backoff: Minimum backoff wait in seconds.
        max_backoff: Maximum backoff wait in seconds.
        continue_on_error: If True, continue after slice failures.
        page_size: Page size for Meta insights API.

    Returns:
        Dict with keys:
            rows: Total rows loaded.
            table: Full BigQuery table path.
            backfill: Backfill result summary dict.

    Raises:
        ValueError: If date range is invalid or granularity is not valid.
        Exception: Re-raises slice errors if continue_on_error is False.
    """
    act = _norm_act(account_id)
    dr = DateRange(
        since=date.fromisoformat(since),
        until=date.fromisoformat(until),
    )

    try:
        slice_granularity = SliceGranularity(granularity.lower())
    except ValueError:
        valid = sorted(e.value for e in SliceGranularity)
        raise ValueError(
            f"Invalid granularity {granularity!r}: must be one of {valid}"
        ) from None

    adapter = MetaAdapter(access_token=access_token)

    # Ensure BQ infrastructure
    ensure_dataset(project_id, dataset)
    ensure_insights_table(project_id, dataset)
    ensure_dim_ad_table(project_id, dataset)

    def _fetch_and_load_slice(window: DateRange) -> int:
        """Fetch a single slice from Meta API and load to BigQuery."""
        rows: list[dict[str, Any]] = []

        for ir in adapter.fetch_insights(
            level=level,
            account_id=act,
            date_range=window,
            page_size=page_size,
        ):
            rows.append(_insight_record_to_bq_row(ir, act))

        if rows:
            load_json_rows(
                project_id=project_id,
                dataset=dataset,
                table=INSIGHTS_TABLE,
                rows=rows,
            )

        return len(rows)

    backfill_result = run_backfill(
        date_range=dr,
        fetch_and_load=_fetch_and_load_slice,
        granularity=slice_granularity,
        max_retries=max_retries,
        min_backoff=min_backoff,
        max_backoff=max_backoff,
        continue_on_error=continue_on_error,
    )

    return {
        "rows": backfill_result.total_rows,
        "table": f"{project_id}.{dataset}.{INSIGHTS_TABLE}",
        "backfill": backfill_result.summary(),
    }
