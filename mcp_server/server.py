"""FastMCP server for PaidSocialNav."""

from __future__ import annotations

import os

from fastmcp import Context, FastMCP
from starlette.responses import JSONResponse

from mcp_server.auth import get_auth_provider
from mcp_server.monitoring import metrics
from mcp_server.prompts import (
    analyze_campaign_performance_prompt,
    audit_setup_wizard_prompt,
    data_sync_planner_prompt,
)
from mcp_server.resources import (
    get_campaign_insights_resource,
    get_tenant_list_resource,
)
from mcp_server.tools import (
    audit_workflow_tool,
    get_tenant_config_tool,
    load_benchmarks_tool,
    meta_sync_insights_tool,
)

# Get authentication provider based on environment
auth = get_auth_provider()

# Create FastMCP server with authentication
mcp = FastMCP(
    "PaidSocialNav",
    instructions="Paid social media advertising audit and analytics platform",
    version="0.1.0",
    auth=auth,
)


# Register Tools
@mcp.tool()
async def meta_sync_insights(
    account_id: str,
    tenant_id: str,
    level: str = "ad",
    date_preset: str | None = None,
    since: str | None = None,
    until: str | None = None,
    ctx: Context | None = None,
) -> dict:
    """Sync Meta advertising insights to BigQuery."""
    return await meta_sync_insights_tool(
        account_id, tenant_id, level, date_preset, since, until, ctx
    )


@mcp.tool()
async def audit_workflow(
    tenant_id: str,
    audit_config: str,
    output_dir: str = "reports/",
    formats: str = "md,html,pdf",
    sheets_export: bool = False,
    ctx: Context | None = None,
) -> dict:
    """Run complete audit workflow with reports and optional AI insights."""
    return await audit_workflow_tool(
        tenant_id, audit_config, output_dir, formats, sheets_export, ctx
    )


@mcp.tool()
async def get_tenant_config(tenant_id: str, ctx: Context | None = None) -> dict:
    """Retrieve tenant configuration details."""
    return await get_tenant_config_tool(tenant_id, ctx)


@mcp.tool()
async def load_benchmarks(
    project_id: str,
    dataset: str,
    csv_path: str,
    ctx: Context | None = None,
) -> dict:
    """Load industry benchmark data from CSV into BigQuery."""
    return await load_benchmarks_tool(project_id, dataset, csv_path, ctx)


# Register Resources
@mcp.resource("tenants://list")
def tenant_list() -> str:
    """List all configured tenants."""
    return get_tenant_list_resource()


@mcp.resource("insights://campaigns/{tenant_id}/{window}")
def campaign_insights(tenant_id: str, window: str) -> str:
    """Retrieve campaign insights for a time window."""
    return get_campaign_insights_resource(tenant_id, window)


# Register Prompts
@mcp.prompt()
def analyze_campaign_performance(
    tenant_name: str,
    overall_score: float,
    formatted_rules: str,
) -> list:
    """Generate strategic insights from audit results."""
    return analyze_campaign_performance_prompt(
        tenant_name, overall_score, formatted_rules
    )


@mcp.prompt()
def audit_setup_wizard(
    tenant_name: str,
    project_id: str,
    dataset: str,
    available_windows: list[str],
) -> list:
    """Guide user through audit configuration."""
    return audit_setup_wizard_prompt(
        tenant_name, project_id, dataset, available_windows
    )


@mcp.prompt()
def data_sync_planner(
    tenant_name: str,
    account_id: str,
    duration: str,
    avg_spend: float,
    windows: list[str],
) -> list:
    """Plan data synchronization strategy."""
    return data_sync_planner_prompt(
        tenant_name, account_id, duration, avg_spend, windows
    )


# Health check endpoint
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request) -> JSONResponse:  # type: ignore[no-untyped-def]
    """Health check endpoint for monitoring."""
    return JSONResponse({"status": "healthy", "service": "PaidSocialNav MCP Server"})


# Metrics endpoint
@mcp.custom_route("/metrics", methods=["GET"])
async def get_metrics_endpoint(request) -> JSONResponse:  # type: ignore[no-untyped-def]
    """Metrics endpoint for monitoring."""
    return JSONResponse(metrics.get_metrics())


if __name__ == "__main__":
    # Run with STDIO for local testing (Phase 1)
    # Run with HTTP for remote deployment (Phase 2)
    transport = os.environ.get("MCP_TRANSPORT", "stdio")

    if transport == "http":
        port = int(os.environ.get("PORT", 8080))
        mcp.run(transport="streamable-http", host="0.0.0.0", port=port)
    else:
        mcp.run(transport="stdio")
