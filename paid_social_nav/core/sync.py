from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from ..adapters.meta.adapter import MetaAdapter
from ..core.enums import DatePreset, Entity
from ..core.models import DateRange
from ..storage.bq import (
    INSIGHTS_TABLE,
    ensure_dataset,
    ensure_insights_table,
    load_json_rows,
)


def _norm_act(account_id: str) -> str:
    return account_id if account_id.startswith("act_") else f"act_{account_id}"


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


def resolve_date_range(
    *,
    date_preset: DatePreset | None,
    since: str | None,
    until: str | None,
) -> DateRange:
    if date_preset and (since or until):
        raise ValueError("--date-preset is mutually exclusive with --since/--until")
    if date_preset:
        rng = _preset_to_range(date_preset)
        if rng is None:
            raise ValueError(
                "'lifetime' is not supported for explicit date ranges in this pipeline"
            )
        s, u = rng
        return DateRange(since=s, until=u)
    if since and until:
        return DateRange(
            since=date.fromisoformat(since), until=date.fromisoformat(until)
        )
    if since or until:
        raise ValueError(
            "Both --since and --until must be provided if not using --date-preset"
        )
    # Default to yesterday when nothing provided
    y = datetime.now(UTC).date() - timedelta(days=1)
    return DateRange(since=y, until=y)


def sync_meta_insights(
    *,
    account_id: str,
    project_id: str,
    dataset: str,
    access_token: str,
    level: Entity = Entity.AD,
    date_preset: DatePreset | None = None,
    since: str | None = None,
    until: str | None = None,
    page_size: int = 500,
) -> dict[str, Any]:
    """Fetch Meta insights (daily) and load to BigQuery.

    Returns a summary dict with row counts.
    """
    act = _norm_act(account_id)
    dr = resolve_date_range(date_preset=date_preset, since=since, until=until)

    adapter = MetaAdapter(access_token=access_token)

    # Ensure BQ dataset/table
    ensure_dataset(project_id, dataset)
    ensure_insights_table(project_id, dataset)

    rows_bq: list[dict[str, Any]] = []

    for ir in adapter.fetch_insights(
        level=level, account_id=act, date_range=dr, page_size=page_size
    ):
        raw = ir.raw or {}
        ad_id = raw.get("ad_id")
        adset_id = raw.get("adset_id")
        campaign_id = raw.get("campaign_id")

        rows_bq.append(
            {
                "date": ir.date.isoformat(),
                "level": ir.level.value,
                "account_global_id": f"meta:account:{act}",
                "campaign_global_id": f"meta:campaign:{campaign_id}"
                if campaign_id
                else None,
                "adset_global_id": f"meta:adset:{adset_id}" if adset_id else None,
                "ad_global_id": f"meta:ad:{ad_id}" if ad_id else None,
                "impressions": ir.impressions,
                "clicks": ir.clicks,
                "spend": ir.spend,
                "conversions": ir.conversions,
                "ctr": ir.ctr,
                "frequency": ir.frequency,
                "raw_metrics": raw,
            }
        )

    if rows_bq:
        load_json_rows(
            project_id=project_id, dataset=dataset, table=INSIGHTS_TABLE, rows=rows_bq
        )

    return {"rows": len(rows_bq), "table": f"{project_id}.{dataset}.{INSIGHTS_TABLE}"}
