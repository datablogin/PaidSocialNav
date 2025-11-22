"""Meta dimension sync functionality."""

from __future__ import annotations

from datetime import UTC, datetime
from time import sleep
from typing import Any

from ..meta.adapter import MetaAdapter
from ...core.logging_config import get_logger
from ...storage.bq import (
    ensure_dataset,
    ensure_dim_account_table,
    ensure_dim_campaign_table,
    ensure_dim_adset_table,
    ensure_dim_ad_table,
    ensure_dim_creative_table,
    upsert_dimension,
)

logger = get_logger(__name__)


def _norm_act(account_id: str) -> str:
    """Normalize account ID to include act_ prefix."""
    return account_id if account_id.startswith("act_") else f"act_{account_id}"


def _parse_timestamp(ts: str | None) -> str | None:
    """Parse and format timestamp from Meta API response."""
    if not ts:
        return None
    try:
        # Meta returns ISO format timestamps
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.isoformat()
    except Exception:
        return None


def _safe_float(value: Any) -> float | None:
    """Safely convert value to float."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def sync_account_dimension(
    *,
    account_id: str,
    project_id: str,
    dataset: str,
    adapter: MetaAdapter,
) -> int:
    """Sync account dimension to BigQuery.

    Args:
        account_id: Meta account ID (with or without act_ prefix)
        project_id: GCP project ID
        dataset: BigQuery dataset name
        adapter: Initialized MetaAdapter instance

    Returns:
        Number of records upserted
    """
    act = _norm_act(account_id)

    logger.info("Fetching account details", extra={"account_id": act})

    try:
        account_data = adapter.fetch_account(act)
    except Exception as e:
        logger.error(
            "Failed to fetch account details",
            extra={"account_id": act, "error": str(e)},
        )
        raise

    # Transform to dimension record
    row = {
        "account_global_id": f"meta:account:{act}",
        "platform_account_id": account_data.get("account_id") or account_data.get("id", ""),
        "account_name": account_data.get("name"),
        "currency": account_data.get("currency"),
        "timezone": account_data.get("timezone_name"),
        "account_status": str(account_data.get("account_status")) if account_data.get("account_status") is not None else None,
        "updated_at": datetime.now(UTC).isoformat(),
        "raw_data": account_data,
    }

    # Ensure table exists and upsert
    ensure_dim_account_table(project_id, dataset)
    count = upsert_dimension(
        project_id=project_id,
        dataset=dataset,
        table_name="dim_account",
        rows=[row],
        merge_key="account_global_id",
    )

    logger.info("Account dimension synced", extra={"count": count})
    return count


def sync_campaign_dimensions(
    *,
    account_id: str,
    project_id: str,
    dataset: str,
    adapter: MetaAdapter,
    page_size: int = 500,
    retries: int = 3,
    retry_backoff: float = 2.0,
) -> int:
    """Sync campaign dimensions to BigQuery.

    Args:
        account_id: Meta account ID (with or without act_ prefix)
        project_id: GCP project ID
        dataset: BigQuery dataset name
        adapter: Initialized MetaAdapter instance
        page_size: Number of records per API page
        retries: Number of retry attempts on failure
        retry_backoff: Backoff time between retries in seconds

    Returns:
        Number of records upserted
    """
    act = _norm_act(account_id)

    logger.info("Fetching campaigns", extra={"account_id": act})

    rows = []
    attempt = 0

    while True:
        try:
            for campaign in adapter.fetch_campaigns(act, page_size=page_size):
                campaign_id = campaign.get("id", "")
                row = {
                    "campaign_global_id": f"meta:campaign:{campaign_id}",
                    "platform_campaign_id": campaign_id,
                    "account_global_id": f"meta:account:{act}",
                    "campaign_name": campaign.get("name"),
                    "campaign_status": campaign.get("status"),
                    "objective": campaign.get("objective"),
                    "buying_type": campaign.get("buying_type"),
                    "daily_budget": _safe_float(campaign.get("daily_budget")),
                    "lifetime_budget": _safe_float(campaign.get("lifetime_budget")),
                    "created_time": _parse_timestamp(campaign.get("created_time")),
                    "updated_at": datetime.now(UTC).isoformat(),
                    "raw_data": campaign,
                }
                rows.append(row)
            break
        except Exception as e:
            attempt += 1
            if attempt > retries:
                logger.error(
                    "Failed to fetch campaigns after retries",
                    extra={"account_id": act, "error": str(e)},
                )
                raise
            backoff_time = retry_backoff * (2 ** (attempt - 1))
            logger.warning(
                "Campaign fetch failed, retrying",
                extra={
                    "account_id": act,
                    "attempt": attempt,
                    "backoff": backoff_time,
                },
            )
            sleep(backoff_time)

    if not rows:
        logger.info("No campaigns found", extra={"account_id": act})
        return 0

    # Ensure table exists and upsert
    ensure_dim_campaign_table(project_id, dataset)
    count = upsert_dimension(
        project_id=project_id,
        dataset=dataset,
        table_name="dim_campaign",
        rows=rows,
        merge_key="campaign_global_id",
    )

    logger.info("Campaign dimensions synced", extra={"count": count})
    return count


def sync_adset_dimensions(
    *,
    account_id: str,
    project_id: str,
    dataset: str,
    adapter: MetaAdapter,
    page_size: int = 500,
    retries: int = 3,
    retry_backoff: float = 2.0,
) -> int:
    """Sync ad set dimensions to BigQuery.

    Args:
        account_id: Meta account ID (with or without act_ prefix)
        project_id: GCP project ID
        dataset: BigQuery dataset name
        adapter: Initialized MetaAdapter instance
        page_size: Number of records per API page
        retries: Number of retry attempts on failure
        retry_backoff: Backoff time between retries in seconds

    Returns:
        Number of records upserted
    """
    act = _norm_act(account_id)

    logger.info("Fetching ad sets", extra={"account_id": act})

    rows = []
    attempt = 0

    while True:
        try:
            for adset in adapter.fetch_adsets(act, page_size=page_size):
                adset_id = adset.get("id", "")
                campaign_id = adset.get("campaign_id", "")
                row = {
                    "adset_global_id": f"meta:adset:{adset_id}",
                    "platform_adset_id": adset_id,
                    "campaign_global_id": f"meta:campaign:{campaign_id}",
                    "account_global_id": f"meta:account:{act}",
                    "adset_name": adset.get("name"),
                    "adset_status": adset.get("status"),
                    "optimization_goal": adset.get("optimization_goal"),
                    "billing_event": adset.get("billing_event"),
                    "bid_strategy": adset.get("bid_strategy"),
                    "daily_budget": _safe_float(adset.get("daily_budget")),
                    "lifetime_budget": _safe_float(adset.get("lifetime_budget")),
                    "start_time": _parse_timestamp(adset.get("start_time")),
                    "end_time": _parse_timestamp(adset.get("end_time")),
                    "created_time": _parse_timestamp(adset.get("created_time")),
                    "updated_at": datetime.now(UTC).isoformat(),
                    "raw_data": adset,
                }
                rows.append(row)
            break
        except Exception as e:
            attempt += 1
            if attempt > retries:
                logger.error(
                    "Failed to fetch ad sets after retries",
                    extra={"account_id": act, "error": str(e)},
                )
                raise
            backoff_time = retry_backoff * (2 ** (attempt - 1))
            logger.warning(
                "Ad set fetch failed, retrying",
                extra={
                    "account_id": act,
                    "attempt": attempt,
                    "backoff": backoff_time,
                },
            )
            sleep(backoff_time)

    if not rows:
        logger.info("No ad sets found", extra={"account_id": act})
        return 0

    # Ensure table exists and upsert
    ensure_dim_adset_table(project_id, dataset)
    count = upsert_dimension(
        project_id=project_id,
        dataset=dataset,
        table_name="dim_adset",
        rows=rows,
        merge_key="adset_global_id",
    )

    logger.info("Ad set dimensions synced", extra={"count": count})
    return count


def sync_ad_dimensions(
    *,
    account_id: str,
    project_id: str,
    dataset: str,
    adapter: MetaAdapter,
    page_size: int = 500,
    retries: int = 3,
    retry_backoff: float = 2.0,
) -> int:
    """Sync ad dimensions to BigQuery.

    Args:
        account_id: Meta account ID (with or without act_ prefix)
        project_id: GCP project ID
        dataset: BigQuery dataset name
        adapter: Initialized MetaAdapter instance
        page_size: Number of records per API page
        retries: Number of retry attempts on failure
        retry_backoff: Backoff time between retries in seconds

    Returns:
        Number of records upserted
    """
    act = _norm_act(account_id)

    logger.info("Fetching ads", extra={"account_id": act})

    rows = []
    attempt = 0

    while True:
        try:
            for ad in adapter.fetch_ads(act, page_size=page_size):
                ad_id = ad.get("id", "")
                adset_id = ad.get("adset_id", "")
                campaign_id = ad.get("campaign_id", "")
                creative = ad.get("creative", {})
                creative_id = creative.get("id", "") if isinstance(creative, dict) else ""

                row = {
                    "ad_global_id": f"meta:ad:{ad_id}",
                    "platform_ad_id": ad_id,
                    "adset_global_id": f"meta:adset:{adset_id}",
                    "campaign_global_id": f"meta:campaign:{campaign_id}",
                    "account_global_id": f"meta:account:{act}",
                    "ad_name": ad.get("name"),
                    "ad_status": ad.get("status"),
                    "creative_global_id": f"meta:creative:{creative_id}" if creative_id else None,
                    "created_time": _parse_timestamp(ad.get("created_time")),
                    "updated_at": datetime.now(UTC).isoformat(),
                    "raw_data": ad,
                }
                rows.append(row)
            break
        except Exception as e:
            attempt += 1
            if attempt > retries:
                logger.error(
                    "Failed to fetch ads after retries",
                    extra={"account_id": act, "error": str(e)},
                )
                raise
            backoff_time = retry_backoff * (2 ** (attempt - 1))
            logger.warning(
                "Ad fetch failed, retrying",
                extra={
                    "account_id": act,
                    "attempt": attempt,
                    "backoff": backoff_time,
                },
            )
            sleep(backoff_time)

    if not rows:
        logger.info("No ads found", extra={"account_id": act})
        return 0

    # Ensure table exists and upsert
    ensure_dim_ad_table(project_id, dataset)
    count = upsert_dimension(
        project_id=project_id,
        dataset=dataset,
        table_name="dim_ad",
        rows=rows,
        merge_key="ad_global_id",
    )

    logger.info("Ad dimensions synced", extra={"count": count})
    return count


def sync_creative_dimensions(
    *,
    account_id: str,
    project_id: str,
    dataset: str,
    adapter: MetaAdapter,
    page_size: int = 500,
    retries: int = 3,
    retry_backoff: float = 2.0,
) -> int:
    """Sync creative dimensions to BigQuery.

    Args:
        account_id: Meta account ID (with or without act_ prefix)
        project_id: GCP project ID
        dataset: BigQuery dataset name
        adapter: Initialized MetaAdapter instance
        page_size: Number of records per API page
        retries: Number of retry attempts on failure
        retry_backoff: Backoff time between retries in seconds

    Returns:
        Number of records upserted
    """
    act = _norm_act(account_id)

    logger.info("Fetching creatives", extra={"account_id": act})

    rows = []
    attempt = 0

    while True:
        try:
            for creative in adapter.fetch_creatives(act, page_size=page_size):
                creative_id = creative.get("id", "")
                row = {
                    "creative_global_id": f"meta:creative:{creative_id}",
                    "platform_creative_id": creative_id,
                    "account_global_id": f"meta:account:{act}",
                    "creative_name": creative.get("name"),
                    "creative_status": creative.get("status"),
                    "title": creative.get("title"),
                    "body": creative.get("body"),
                    "call_to_action": creative.get("call_to_action_type"),
                    "image_url": creative.get("image_url"),
                    "video_url": creative.get("video_id"),
                    "thumbnail_url": creative.get("thumbnail_url"),
                    "created_time": None,  # Not typically available in creative endpoint
                    "updated_at": datetime.now(UTC).isoformat(),
                    "raw_data": creative,
                }
                rows.append(row)
            break
        except Exception as e:
            attempt += 1
            if attempt > retries:
                logger.error(
                    "Failed to fetch creatives after retries",
                    extra={"account_id": act, "error": str(e)},
                )
                raise
            backoff_time = retry_backoff * (2 ** (attempt - 1))
            logger.warning(
                "Creative fetch failed, retrying",
                extra={
                    "account_id": act,
                    "attempt": attempt,
                    "backoff": backoff_time,
                },
            )
            sleep(backoff_time)

    if not rows:
        logger.info("No creatives found", extra={"account_id": act})
        return 0

    # Ensure table exists and upsert
    ensure_dim_creative_table(project_id, dataset)
    count = upsert_dimension(
        project_id=project_id,
        dataset=dataset,
        table_name="dim_creative",
        rows=rows,
        merge_key="creative_global_id",
    )

    logger.info("Creative dimensions synced", extra={"count": count})
    return count


def sync_all_dimensions(
    *,
    account_id: str,
    project_id: str,
    dataset: str,
    access_token: str,
    page_size: int = 500,
    retries: int = 3,
    retry_backoff: float = 2.0,
) -> dict[str, int]:
    """Sync all Meta dimensions to BigQuery.

    Args:
        account_id: Meta account ID (with or without act_ prefix)
        project_id: GCP project ID
        dataset: BigQuery dataset name
        access_token: Meta API access token
        page_size: Number of records per API page
        retries: Number of retry attempts on failure
        retry_backoff: Backoff time between retries in seconds

    Returns:
        Dictionary with counts for each dimension type
    """
    act = _norm_act(account_id)

    logger.info("Starting dimension sync", extra={"account_id": act})

    # Ensure dataset exists
    ensure_dataset(project_id, dataset)

    # Initialize adapter
    adapter = MetaAdapter(access_token=access_token)

    # Sync each dimension type
    counts = {}

    # 1. Account (single record)
    counts["account"] = sync_account_dimension(
        account_id=act,
        project_id=project_id,
        dataset=dataset,
        adapter=adapter,
    )

    # 2. Campaigns
    counts["campaigns"] = sync_campaign_dimensions(
        account_id=act,
        project_id=project_id,
        dataset=dataset,
        adapter=adapter,
        page_size=page_size,
        retries=retries,
        retry_backoff=retry_backoff,
    )

    # 3. Ad Sets
    counts["adsets"] = sync_adset_dimensions(
        account_id=act,
        project_id=project_id,
        dataset=dataset,
        adapter=adapter,
        page_size=page_size,
        retries=retries,
        retry_backoff=retry_backoff,
    )

    # 4. Ads
    counts["ads"] = sync_ad_dimensions(
        account_id=act,
        project_id=project_id,
        dataset=dataset,
        adapter=adapter,
        page_size=page_size,
        retries=retries,
        retry_backoff=retry_backoff,
    )

    # 5. Creatives
    counts["creatives"] = sync_creative_dimensions(
        account_id=act,
        project_id=project_id,
        dataset=dataset,
        adapter=adapter,
        page_size=page_size,
        retries=retries,
        retry_backoff=retry_backoff,
    )

    logger.info("Dimension sync complete", extra={"counts": counts})

    return counts
