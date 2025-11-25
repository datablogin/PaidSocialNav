"""MCP tools for PaidSocialNav operations."""

from __future__ import annotations

import os
import re
from typing import Any

from fastmcp import Context

from paid_social_nav.core.enums import DatePreset, Entity
from paid_social_nav.core.sync import sync_meta_insights
from paid_social_nav.core.tenants import get_tenant
from paid_social_nav.skills.audit_workflow import AuditWorkflowSkill
from paid_social_nav.storage.bq import load_benchmarks_csv


class ValidationError(ValueError):
    """Raised when input validation fails."""

    pass


async def meta_sync_insights_tool(
    account_id: str,
    tenant_id: str,
    level: Entity | str = "ad",
    date_preset: DatePreset | str | None = None,
    since: str | None = None,
    until: str | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """
    Sync Meta advertising insights to BigQuery.

    Fetches campaign data from Meta Graph API and loads into BigQuery data warehouse.

    Args:
        account_id: Meta ad account ID (e.g., "act_123456789" or "123456789")
        tenant_id: Tenant ID from configs/tenants.yaml
        level: Aggregation level (Entity enum or string: ad, adset, campaign)
        date_preset: Named date range (DatePreset enum or string: yesterday, last_7d, last_28d, etc.)
        since: Start date (YYYY-MM-DD) if not using preset
        until: End date (YYYY-MM-DD) if not using preset

    Returns:
        Success: {"success": True, "rows": int, "table": str, "message": str}
        Failure: {"success": False, "error": str, "message": str}

    Raises:
        ValidationError: If account_id format is invalid or level is not allowed
        ValueError: If tenant not found or META_ACCESS_TOKEN not set
    """
    try:
        # Validate account_id format (must be act_<digits> or just digits)
        if not re.match(r"^(act_)?\d+$", account_id):
            raise ValidationError(
                f"Invalid account_id format: '{account_id}'. "
                "Must be 'act_123456789' or '123456789'"
            )

        # Normalize account_id to include 'act_' prefix
        if not account_id.startswith("act_"):
            account_id = f"act_{account_id}"

        # Normalize level to Entity enum (accept both string and enum for MCP compatibility)
        if isinstance(level, str):
            allowed_levels = {"ad", "adset", "campaign"}
            if level.lower() not in allowed_levels:
                raise ValidationError(
                    f"Invalid level: '{level}'. Must be one of: {', '.join(allowed_levels)}"
                )
            level_enum = Entity(level.lower())
        else:
            level_enum = level

        # Normalize date preset to DatePreset enum if provided
        if isinstance(date_preset, str):
            preset_enum = DatePreset(date_preset.upper())
        else:
            preset_enum = date_preset

        if ctx:
            await ctx.info(f"Starting sync for account {account_id} at {level_enum.value} level")

        # Get tenant configuration
        tenant = get_tenant(tenant_id)
        if not tenant:
            raise ValueError(f"Tenant '{tenant_id}' not found")

        # Get access token from environment
        access_token = os.environ.get("META_ACCESS_TOKEN")
        if not access_token:
            raise ValueError("META_ACCESS_TOKEN environment variable not set")

        if ctx:
            await ctx.info(f"Syncing to {tenant.project_id}.{tenant.dataset}")

        # Call existing sync function from paid_social_nav.core.sync:102
        result = sync_meta_insights(
            account_id=account_id,
            project_id=tenant.project_id,
            dataset=tenant.dataset,
            access_token=access_token,
            level=level_enum,
            date_preset=preset_enum,
            since=since,
            until=until,
        )

        rows = result.get("rows_loaded", 0)

        if ctx:
            await ctx.info(f"Sync complete: {rows} rows loaded")

        return {
            "success": True,
            "rows": rows,
            "table": f"{tenant.project_id}.{tenant.dataset}.fct_ad_insights_daily",
            "message": f"Successfully synced {rows} insights records",
        }

    except Exception as e:
        if ctx:
            await ctx.error(f"Sync failed: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to sync insights: {str(e)}",
        }


async def audit_workflow_tool(
    tenant_id: str,
    audit_config: str,
    output_dir: str = "reports/",
    formats: str = "md,html,pdf",
    sheets_export: bool = False,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """
    Run complete audit workflow with reports and optional AI insights.

    Executes audit analysis, generates multi-format reports, and optionally
    creates Google Sheets export for drill-down analysis.

    Args:
        tenant_id: Tenant identifier from configs/tenants.yaml
        audit_config: Path to audit configuration YAML file
        output_dir: Directory for output files
        formats: Comma-separated output formats (md, html, pdf)
        sheets_export: Whether to export to Google Sheets

    Returns:
        Success: {
            "success": True,
            "audit_score": float,
            "reports": {"md": str, "html": str, "pdf": str},
            "sheet_url": str | None,
            "message": str
        }
        Failure: {
            "success": False,
            "error": str,
            "message": str
        }

    Raises:
        ValueError: If tenant not found or audit configuration is invalid
        FileNotFoundError: If audit config file doesn't exist
    """
    try:
        if ctx:
            await ctx.info(f"Starting audit workflow for tenant: {tenant_id}")
            await ctx.report_progress(0, 5)

        # Use existing AuditWorkflowSkill from paid_social_nav.skills.audit_workflow:22
        skill = AuditWorkflowSkill()

        # Build context
        context = {
            "tenant_id": tenant_id,
            "audit_config": audit_config,
            "output_dir": output_dir,
            "formats": formats.split(","),
            "sheets_export": sheets_export,
        }

        if ctx:
            await ctx.report_progress(1, 5)
            await ctx.info("Validating configuration...")

        # Execute workflow
        result = skill.execute(context)

        if ctx:
            await ctx.report_progress(5, 5)
            if result.success:
                audit_score = result.data.get("audit_score", 0)
                await ctx.info(f"Audit complete with score: {audit_score:.1f}")
            else:
                await ctx.error(f"Audit failed: {result.message}")

        return {
            "success": result.success,
            "message": result.message,
            **result.data,
        }

    except Exception as e:
        if ctx:
            await ctx.error(f"Audit workflow failed: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "message": f"Audit workflow failed: {str(e)}",
        }


async def get_tenant_config_tool(
    tenant_id: str, ctx: Context | None = None
) -> dict[str, Any]:
    """
    Retrieve tenant configuration details.

    Args:
        tenant_id: Tenant identifier

    Returns:
        Success: {
            "success": True,
            "id": str,
            "project_id": str,
            "dataset": str,
            "default_level": str
        }
        Failure: {
            "success": False,
            "error": str,
            "message": str
        }

    Raises:
        ValueError: If tenant_id is not found in configuration
    """
    try:
        # Use existing get_tenant from paid_social_nav.core.tenants:27
        tenant = get_tenant(tenant_id)

        if not tenant:
            if ctx:
                await ctx.error(f"Tenant '{tenant_id}' not found")
            return {
                "success": False,
                "error": "not_found",
                "message": f"Tenant '{tenant_id}' not found",
            }

        if ctx:
            await ctx.info(f"Retrieved config for tenant: {tenant_id}")

        return {
            "success": True,
            "id": tenant.id,
            "project_id": tenant.project_id,
            "dataset": tenant.dataset,
            "default_level": (
                tenant.default_level.value if tenant.default_level else None
            ),
        }

    except Exception as e:
        if ctx:
            await ctx.error(f"Failed to get tenant config: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to retrieve tenant config: {str(e)}",
        }


async def load_benchmarks_tool(
    project_id: str,
    dataset: str,
    csv_path: str,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """
    Load industry benchmark data from CSV into BigQuery.

    Args:
        project_id: GCP project ID
        dataset: BigQuery dataset name
        csv_path: Path to benchmarks CSV file

    Returns:
        Success: {
            "success": True,
            "rows_loaded": int,
            "table": str,
            "message": str
        }
        Failure: {
            "success": False,
            "error": str,
            "message": str
        }

    Raises:
        FileNotFoundError: If csv_path doesn't exist
        ValueError: If CSV format is invalid or BigQuery load fails
    """
    try:
        if ctx:
            await ctx.info(f"Loading benchmarks from {csv_path}")

        # Use existing load_benchmarks_csv from paid_social_nav.storage.bq:330
        rows = load_benchmarks_csv(
            project_id=project_id, dataset=dataset, csv_path=csv_path
        )

        if ctx:
            await ctx.info(f"Loaded {rows} benchmark records")

        return {
            "success": True,
            "rows_loaded": rows,
            "table": f"{project_id}.{dataset}.benchmarks_performance",
            "message": f"Successfully loaded {rows} benchmark records",
        }

    except Exception as e:
        if ctx:
            await ctx.error(f"Failed to load benchmarks: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to load benchmarks: {str(e)}",
        }
