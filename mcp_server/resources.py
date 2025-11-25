"""MCP resources for PaidSocialNav data access."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from paid_social_nav.core.tenants import get_tenant
from paid_social_nav.storage.bq import BQClient


def list_tenants() -> list[dict[str, Any]]:
    """List all configured tenants from configs/tenants.yaml."""
    cfg_path = Path("configs/tenants.yaml")
    if not cfg_path.exists():
        return []

    with cfg_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    tenants_data = data.get("tenants", {})

    # Build tenant list directly without extra lookups to avoid N+1 query pattern
    return [
        {
            "id": tenant_id,
            "project_id": cfg.get("project_id"),
            "dataset": cfg.get("dataset", "paid_social"),
            "default_level": cfg.get("default_level", "campaign"),
        }
        for tenant_id, cfg in tenants_data.items()
    ]


def get_tenant_list_resource() -> str:
    """
    List all configured tenants.

    URI: tenants://list
    """
    tenants = list_tenants()
    return json.dumps({"tenants": tenants}, indent=2)


def get_campaign_insights_resource(tenant_id: str, window: str) -> str:
    """
    Retrieve campaign insights for a time window.

    URI: insights://campaigns/{tenant_id}/{window}

    Args:
        tenant_id: Tenant identifier
        window: Time window (last_7d, last_14d, last_28d, last_30d)
    """
    tenant = get_tenant(tenant_id)
    if not tenant:
        return json.dumps(
            {"error": f"Tenant '{tenant_id}' not found"}, indent=2
        )

    bq = BQClient(tenant.project_id)

    # Map window to date ranges
    window_days = {
        "last_7d": 7,
        "last_14d": 14,
        "last_28d": 28,
        "last_30d": 30,
    }

    days = window_days.get(window, 7)

    query = f"""
    SELECT
        date,
        level,
        campaign_global_id,
        SUM(impressions) as impressions,
        SUM(clicks) as clicks,
        SUM(spend) as spend,
        SUM(conversions) as conversions,
        AVG(ctr) as ctr,
        AVG(frequency) as frequency
    FROM `{tenant.project_id}.{tenant.dataset}.fct_ad_insights_daily`
    WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL @days DAY)
      AND level = 'campaign'
    GROUP BY 1, 2, 3
    ORDER BY date DESC, spend DESC
    LIMIT 1000
    """

    try:
        rows = bq.query_rows(query, params={"days": days})
        return json.dumps(rows, indent=2, default=str)
    except Exception as e:
        return json.dumps(
            {"error": f"Failed to query insights: {str(e)}"}, indent=2
        )
