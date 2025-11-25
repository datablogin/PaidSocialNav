---
date: 2025-11-23T22:19:49+0000
author: Robert Welborn
git_commit: fc96e5267179e423c6eec3b04571f1d8fdb6c0ef
branch: feature/issues-27-29-logging-output-formatting
repository: datablogin/PaidSocialNav
topic: "FastMCP Remote Server Implementation Plan"
tags: [plan, mcp, fastmcp, deployment, cloud-run, architecture]
status: draft
related_research: thoughts/shared/research/2025-11-22-claude-skills-mcp-architecture-evaluation.md
---

# Implementation Plan: PaidSocialNav FastMCP Remote Server

**Date**: 2025-11-23T22:19:49+0000
**Author**: Robert Welborn
**Repository**: datablogin/PaidSocialNav
**Related Research**: [Claude Skills/MCP Architecture Evaluation](../research/2025-11-22-claude-skills-mcp-architecture-evaluation.md)

## Executive Summary

This plan details the implementation of a FastMCP server that exposes the PaidSocialNav platform as a remote MCP service, enabling AI assistants (Claude, etc.) to access paid social media auditing capabilities via the Model Context Protocol. This maintains all the robust work already completed while adding a conversational AI interface layer.

**Key Decision**: Use FastMCP for rapid development and deploy to Google Cloud Run for production-ready remote access with OAuth authentication.

## Architecture Overview

### Current Architecture (Preserved)
```
┌─────────────────────────────────────────────────────────────┐
│                    PaidSocialNav Core                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  Adapters    │  │  Sync/Audit  │  │   Reports    │     │
│  │  (Meta API)  │→ │   Engine     │→ │  (MD/HTML)   │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│         ↓                  ↓                  ↓              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │            BigQuery Data Warehouse                    │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                           ↑
                           │ (import and use)
                           │
┌─────────────────────────────────────────────────────────────┐
│                   NEW: FastMCP Server Layer                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Tools      │  │  Resources   │  │   Prompts    │     │
│  │ (Actions)    │  │ (Data)       │  │ (Templates)  │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
                           ↓
                      HTTP Stream
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                   Google Cloud Run                           │
│  - Authenticated via Google OAuth                            │
│  - Horizontal scaling                                         │
│  - Zero-downtime deployments                                 │
└─────────────────────────────────────────────────────────────┘
                           ↓
                      MCP Protocol
                           ↓
┌─────────────────────────────────────────────────────────────┐
│           AI Clients (Claude, other MCP clients)            │
└─────────────────────────────────────────────────────────────┘
```

### Design Principles

1. **Separation of Concerns**: MCP server is a thin wrapper, core logic stays in `paid_social_nav` package
2. **Reuse, Don't Rewrite**: Import and call existing functions from CLI/skills modules
3. **Security First**: OAuth authentication, input validation, no credential exposure
4. **Production Ready**: Proper error handling, logging, testing, monitoring
5. **Cost Efficient**: Leverage Cloud Run's scale-to-zero and per-request billing

## Phase 1: Local FastMCP Server (STDIO)

**Goal**: Create working MCP server for local testing with Claude Desktop

**Duration**: 1-2 days

**Deliverables**:
- `mcp_server/server.py` - FastMCP server implementation
- `mcp_server/__init__.py` - Package setup
- Claude Desktop config for local testing
- Basic integration tests

### 1.1 Project Structure

```
PaidSocialNav/
├── paid_social_nav/          # Existing core package (unchanged)
├── mcp_server/               # NEW: MCP server package
│   ├── __init__.py
│   ├── server.py            # Main FastMCP server
│   ├── tools.py             # MCP tool definitions
│   ├── resources.py         # MCP resource definitions
│   ├── prompts.py           # MCP prompt templates
│   ├── auth.py              # Authentication utilities
│   └── config.py            # Server configuration
├── tests/
│   └── test_mcp_server.py   # NEW: MCP server tests
├── pyproject.toml           # Update with fastmcp dependency
├── Dockerfile               # NEW: For Cloud Run deployment
└── .env.example             # Update with MCP-specific vars
```

### 1.2 Core Tools Implementation

**File**: `mcp_server/tools.py`

```python
"""MCP tools for PaidSocialNav operations."""
from typing import Any
from fastmcp import Context
from paid_social_nav.core.sync import sync_meta_insights
from paid_social_nav.audit.engine import AuditEngine
from paid_social_nav.skills.audit_workflow import AuditWorkflowSkill
from paid_social_nav.core.tenants import get_tenant
from paid_social_nav.storage.bq import load_benchmarks_csv
import json

async def meta_sync_insights_tool(
    account_id: str,
    level: str = "ad",
    date_preset: str | None = None,
    since: str | None = None,
    until: str | None = None,
    tenant: str | None = None,
    ctx: Context | None = None
) -> dict[str, Any]:
    """
    Sync Meta advertising insights to BigQuery.

    Fetches campaign data from Meta Graph API and loads into BigQuery data warehouse.

    Args:
        account_id: Meta ad account ID (e.g., "act_123456789")
        level: Aggregation level (ad, adset, or campaign)
        date_preset: Named date range (yesterday, last_7d, last_28d, etc.)
        since: Start date (YYYY-MM-DD) if not using preset
        until: End date (YYYY-MM-DD) if not using preset
        tenant: Tenant ID from configs/tenants.yaml

    Returns:
        {"rows": int, "table": str, "success": bool}
    """
    try:
        if ctx:
            await ctx.info(f"Starting sync for account {account_id} at {level} level")

        # Call existing sync function
        rows = await sync_meta_insights(
            account_id=account_id,
            level=level,
            date_preset=date_preset,
            since=since,
            until=until,
            tenant=tenant
        )

        if ctx:
            await ctx.info(f"Sync complete: {rows} rows loaded")

        return {
            "success": True,
            "rows": rows,
            "table": f"{tenant}.paid_social.fct_ad_insights_daily" if tenant else "unknown",
            "message": f"Successfully synced {rows} insights records"
        }

    except Exception as e:
        if ctx:
            await ctx.error(f"Sync failed: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to sync insights: {str(e)}"
        }


async def audit_workflow_tool(
    tenant_id: str,
    audit_config: str,
    output_dir: str = "reports/",
    formats: str = "md,html,pdf",
    sheets_export: bool = False,
    ctx: Context | None = None
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
        {
            "success": bool,
            "audit_score": float,
            "reports": {"md": str, "html": str, "pdf": str},
            "sheet_url": str | None
        }
    """
    try:
        if ctx:
            await ctx.info(f"Starting audit workflow for tenant: {tenant_id}")
            await ctx.report_progress(0, 5)

        # Create skill instance
        skill = AuditWorkflowSkill()

        # Build context
        context = {
            "tenant_id": tenant_id,
            "audit_config": audit_config,
            "output_dir": output_dir,
            "formats": formats.split(","),
            "sheets_export": sheets_export
        }

        if ctx:
            await ctx.report_progress(1, 5)
            await ctx.info("Validating configuration...")

        # Execute workflow
        result = skill.execute(context)

        if ctx:
            await ctx.report_progress(5, 5)
            if result.success:
                await ctx.info(f"Audit complete with score: {result.data.get('audit_score', 0):.1f}")
            else:
                await ctx.error(f"Audit failed: {result.message}")

        return {
            "success": result.success,
            "message": result.message,
            **result.data
        }

    except Exception as e:
        if ctx:
            await ctx.error(f"Audit workflow failed: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "message": f"Audit workflow failed: {str(e)}"
        }


async def get_tenant_config_tool(tenant_id: str, ctx: Context | None = None) -> dict[str, Any]:
    """
    Retrieve tenant configuration details.

    Args:
        tenant_id: Tenant identifier

    Returns:
        {"id": str, "project_id": str, "dataset": str, "default_level": str}
    """
    try:
        tenant = get_tenant(tenant_id)

        if ctx:
            await ctx.info(f"Retrieved config for tenant: {tenant_id}")

        return {
            "success": True,
            "id": tenant.id,
            "project_id": tenant.project_id,
            "dataset": tenant.dataset,
            "default_level": tenant.default_level
        }

    except Exception as e:
        if ctx:
            await ctx.error(f"Failed to get tenant config: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "message": f"Tenant '{tenant_id}' not found"
        }


async def load_benchmarks_tool(
    project_id: str,
    dataset: str,
    csv_path: str,
    ctx: Context | None = None
) -> dict[str, Any]:
    """
    Load industry benchmark data from CSV into BigQuery.

    Args:
        project_id: GCP project ID
        dataset: BigQuery dataset name
        csv_path: Path to benchmarks CSV file

    Returns:
        {"rows_loaded": int, "table": str, "success": bool}
    """
    try:
        if ctx:
            await ctx.info(f"Loading benchmarks from {csv_path}")

        rows = await load_benchmarks_csv(project_id, dataset, csv_path)

        if ctx:
            await ctx.info(f"Loaded {rows} benchmark records")

        return {
            "success": True,
            "rows_loaded": rows,
            "table": f"{project_id}.{dataset}.benchmarks_performance",
            "message": f"Successfully loaded {rows} benchmark records"
        }

    except Exception as e:
        if ctx:
            await ctx.error(f"Failed to load benchmarks: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to load benchmarks: {str(e)}"
        }
```

### 1.3 Core Resources Implementation

**File**: `mcp_server/resources.py`

```python
"""MCP resources for PaidSocialNav data access."""
from typing import Any
from paid_social_nav.storage.bq import BQClient
from paid_social_nav.core.tenants import get_tenant, list_tenants
import json

def get_tenant_list_resource() -> str:
    """
    List all configured tenants.

    URI: tenants://list
    """
    tenants = list_tenants()
    return json.dumps(
        {
            "tenants": [
                {
                    "id": t.id,
                    "project_id": t.project_id,
                    "dataset": t.dataset,
                    "default_level": t.default_level
                }
                for t in tenants
            ]
        },
        indent=2
    )


def get_audit_results_resource(tenant_id: str, date: str) -> str:
    """
    Retrieve audit results for a specific date.

    URI: audit://results/{tenant_id}/{date}

    Args:
        tenant_id: Tenant identifier
        date: Audit date (YYYY-MM-DD)
    """
    tenant = get_tenant(tenant_id)
    bq = BQClient(tenant.project_id)

    # Query audit results (this would need an audit_results table)
    query = """
    SELECT
        audit_date,
        overall_score,
        rule_results
    FROM `{project}.{dataset}.audit_results`
    WHERE tenant_id = @tenant_id
      AND audit_date = @date
    ORDER BY audit_date DESC
    LIMIT 1
    """.format(project=tenant.project_id, dataset=tenant.dataset)

    rows = bq.query_rows(
        query,
        params={"tenant_id": tenant_id, "date": date}
    )

    return json.dumps(rows[0] if rows else {"error": "No results found"}, indent=2)


def get_campaign_insights_resource(tenant_id: str, window: str) -> str:
    """
    Retrieve campaign insights for a time window.

    URI: insights://campaigns/{tenant_id}/{window}

    Args:
        tenant_id: Tenant identifier
        window: Time window (last_7d, last_28d, etc.)
    """
    tenant = get_tenant(tenant_id)
    bq = BQClient(tenant.project_id)

    # Map window to date ranges
    window_days = {
        "last_7d": 7,
        "last_14d": 14,
        "last_28d": 28,
        "last_30d": 30
    }

    days = window_days.get(window, 7)

    query = """
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
    FROM `{project}.{dataset}.fct_ad_insights_daily`
    WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL @days DAY)
      AND level = 'campaign'
    GROUP BY 1, 2, 3
    ORDER BY date DESC, spend DESC
    """.format(project=tenant.project_id, dataset=tenant.dataset)

    rows = bq.query_rows(query, params={"days": days})

    return json.dumps(rows, indent=2)


def get_benchmarks_resource(industry: str, region: str, spend_band: str) -> str:
    """
    Retrieve industry benchmark data.

    URI: benchmarks://{industry}/{region}/{spend_band}

    Args:
        industry: Industry category (retail, finance, etc.)
        region: Geographic region (US, EU, etc.)
        spend_band: Spend range (10k-50k, 50k-100k, etc.)
    """
    # This would query from benchmarks_performance table
    # Using a placeholder for now
    query = """
    SELECT
        metric_name,
        p25, p50, p75, p90
    FROM `project.dataset.benchmarks_performance`
    WHERE industry = @industry
      AND region = @region
      AND spend_band = @spend_band
    """

    # Placeholder data
    return json.dumps({
        "industry": industry,
        "region": region,
        "spend_band": spend_band,
        "metrics": {
            "ctr": {"p25": 0.01, "p50": 0.015, "p75": 0.022, "p90": 0.030},
            "cpm": {"p25": 5.00, "p50": 7.50, "p75": 10.00, "p90": 15.00},
            "frequency": {"p25": 1.5, "p50": 2.0, "p75": 2.8, "p90": 3.5}
        }
    }, indent=2)
```

### 1.4 Prompts Implementation

**File**: `mcp_server/prompts.py`

```python
"""MCP prompts for PaidSocialNav workflows."""
from fastmcp.prompts.prompt import PromptMessage, TextContent

def analyze_campaign_performance_prompt(
    tenant_name: str,
    overall_score: float,
    formatted_rules: str
) -> list[PromptMessage]:
    """
    Generate strategic insights from audit results.

    Args:
        tenant_name: Client/tenant name
        overall_score: Overall audit score (0-100)
        formatted_rules: Formatted rule results
    """
    prompt_text = f"""Analyze the paid social campaign performance for {tenant_name}:

Overall Score: {overall_score:.1f}/100

Key Findings:
{formatted_rules}

Provide:
1. Top 3 strengths (what's working well)
2. Top 3 critical issues with severity levels (high/medium/low)
3. 5 strategic recommendations with effort estimates
4. Quick wins (immediate actions that can be taken)
5. 90-day implementation roadmap (phased approach)

Focus on actionable insights that will improve campaign performance."""

    return [
        PromptMessage(
            role="user",
            content=TextContent(type="text", text=prompt_text)
        )
    ]


def audit_setup_wizard_prompt(
    tenant_name: str,
    project_id: str,
    dataset: str,
    available_windows: list[str]
) -> list[PromptMessage]:
    """
    Guide user through audit configuration.

    Args:
        tenant_name: Client/tenant name
        project_id: GCP project ID
        dataset: BigQuery dataset
        available_windows: List of available time windows
    """
    prompt_text = f"""Help me set up a paid social audit for {tenant_name}.

Current configuration:
- GCP Project: {project_id}
- Dataset: {dataset}
- Available windows: {', '.join(available_windows)}

Guide me through:
1. Selecting appropriate audit level (account/campaign/adset/ad)
2. Choosing time windows to analyze
3. Setting rule weights based on business priorities
4. Configuring thresholds appropriate for industry
5. Mapping to benchmark data (industry/region/spend_band)

Ask clarifying questions to understand the business context and objectives."""

    return [
        PromptMessage(
            role="user",
            content=TextContent(type="text", text=prompt_text)
        )
    ]


def data_sync_planner_prompt(
    tenant_name: str,
    account_id: str,
    duration: str,
    avg_spend: float,
    windows: list[str]
) -> str:
    """
    Plan data synchronization strategy.

    Args:
        tenant_name: Client/tenant name
        account_id: Meta ad account ID
        duration: How long account has been running
        avg_spend: Average daily spend
        windows: Required analysis windows
    """
    return f"""Plan a data sync strategy for {tenant_name} Meta account {account_id}.

Requirements:
- Account has been running for: {duration}
- Average daily spend: ${avg_spend:.2f}
- Need data for analysis windows: {', '.join(windows)}

Recommend:
1. Optimal sync levels (ad/adset/campaign) based on scale
2. Date range strategy (presets vs. explicit dates)
3. Chunking configuration for large ranges
4. Fallback strategy between levels
5. Retry and rate limiting settings

Consider data volume, API costs, and analysis requirements."""
```

### 1.5 Main Server Implementation

**File**: `mcp_server/server.py`

```python
"""FastMCP server for PaidSocialNav."""
from fastmcp import FastMCP, Context
from mcp_server.tools import (
    meta_sync_insights_tool,
    audit_workflow_tool,
    get_tenant_config_tool,
    load_benchmarks_tool
)
from mcp_server.resources import (
    get_tenant_list_resource,
    get_audit_results_resource,
    get_campaign_insights_resource,
    get_benchmarks_resource
)
from mcp_server.prompts import (
    analyze_campaign_performance_prompt,
    audit_setup_wizard_prompt,
    data_sync_planner_prompt
)
import os

# Create FastMCP server
mcp = FastMCP(
    "PaidSocialNav",
    version="0.1.0",
    description="Paid social media advertising audit and analytics platform"
)

# Register Tools
@mcp.tool()
async def meta_sync_insights(
    account_id: str,
    level: str = "ad",
    date_preset: str | None = None,
    since: str | None = None,
    until: str | None = None,
    tenant: str | None = None,
    ctx: Context = None
):
    """Sync Meta advertising insights to BigQuery."""
    return await meta_sync_insights_tool(
        account_id, level, date_preset, since, until, tenant, ctx
    )


@mcp.tool()
async def audit_workflow(
    tenant_id: str,
    audit_config: str,
    output_dir: str = "reports/",
    formats: str = "md,html,pdf",
    sheets_export: bool = False,
    ctx: Context = None
):
    """Run complete audit workflow with reports and optional AI insights."""
    return await audit_workflow_tool(
        tenant_id, audit_config, output_dir, formats, sheets_export, ctx
    )


@mcp.tool()
async def get_tenant_config(tenant_id: str, ctx: Context = None):
    """Retrieve tenant configuration details."""
    return await get_tenant_config_tool(tenant_id, ctx)


@mcp.tool()
async def load_benchmarks(
    project_id: str,
    dataset: str,
    csv_path: str,
    ctx: Context = None
):
    """Load industry benchmark data from CSV into BigQuery."""
    return await load_benchmarks_tool(project_id, dataset, csv_path, ctx)


# Register Resources
@mcp.resource("tenants://list")
def tenant_list():
    """List all configured tenants."""
    return get_tenant_list_resource()


@mcp.resource("audit://results/{tenant_id}/{date}")
def audit_results(tenant_id: str, date: str):
    """Retrieve audit results for a specific date."""
    return get_audit_results_resource(tenant_id, date)


@mcp.resource("insights://campaigns/{tenant_id}/{window}")
def campaign_insights(tenant_id: str, window: str):
    """Retrieve campaign insights for a time window."""
    return get_campaign_insights_resource(tenant_id, window)


@mcp.resource("benchmarks://{industry}/{region}/{spend_band}")
def benchmarks(industry: str, region: str, spend_band: str):
    """Retrieve industry benchmark data."""
    return get_benchmarks_resource(industry, region, spend_band)


# Register Prompts
@mcp.prompt()
def analyze_campaign_performance(
    tenant_name: str,
    overall_score: float,
    formatted_rules: str
):
    """Generate strategic insights from audit results."""
    return analyze_campaign_performance_prompt(
        tenant_name, overall_score, formatted_rules
    )


@mcp.prompt()
def audit_setup_wizard(
    tenant_name: str,
    project_id: str,
    dataset: str,
    available_windows: list[str]
):
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
    windows: list[str]
):
    """Plan data synchronization strategy."""
    return data_sync_planner_prompt(
        tenant_name, account_id, duration, avg_spend, windows
    )


# Health check endpoint
@mcp.custom_route("/health", methods=["GET"])
def health_check():
    """Health check endpoint for monitoring."""
    return {"status": "healthy", "service": "PaidSocialNav MCP Server"}


if __name__ == "__main__":
    # Run with STDIO for local testing
    # Run with HTTP for remote deployment
    transport = os.environ.get("MCP_TRANSPORT", "stdio")

    if transport == "http":
        port = int(os.environ.get("PORT", 8080))
        mcp.run(
            transport="streamable-http",
            host="0.0.0.0",
            port=port
        )
    else:
        mcp.run(transport="stdio")
```

### 1.6 Testing Setup

**File**: `tests/test_mcp_server.py`

```python
"""Tests for PaidSocialNav MCP server."""
import pytest
from fastmcp import Client
from mcp_server.server import mcp

@pytest.fixture
async def mcp_client():
    """Reusable MCP client fixture."""
    async with Client(mcp) as client:
        yield client


async def test_list_tools(mcp_client):
    """Test tool listing."""
    tools = await mcp_client.list_tools()
    tool_names = [t.name for t in tools]

    assert "meta_sync_insights" in tool_names
    assert "audit_workflow" in tool_names
    assert "get_tenant_config" in tool_names
    assert "load_benchmarks" in tool_names


async def test_list_resources(mcp_client):
    """Test resource listing."""
    resources = await mcp_client.list_resources()
    # Verify resource URI templates are registered
    assert len(resources) > 0


async def test_list_prompts(mcp_client):
    """Test prompt listing."""
    prompts = await mcp_client.list_prompts()
    prompt_names = [p.name for p in prompts]

    assert "analyze_campaign_performance" in prompt_names
    assert "audit_setup_wizard" in prompt_names


async def test_get_tenant_config(mcp_client):
    """Test tenant config retrieval."""
    result = await mcp_client.call_tool(
        "get_tenant_config",
        {"tenant_id": "puttery"}
    )

    assert result.success is True
    assert result.data["id"] == "puttery"
    assert "project_id" in result.data


async def test_tenant_list_resource(mcp_client):
    """Test tenant list resource."""
    resource = await mcp_client.read_resource("tenants://list")
    assert len(resource) > 0
    # Should return JSON with tenant list


@pytest.mark.parametrize(
    "tenant_id,expected_success",
    [
        ("puttery", True),
        ("fleming", True),
        ("nonexistent", False)
    ]
)
async def test_get_tenant_config_validation(
    mcp_client,
    tenant_id: str,
    expected_success: bool
):
    """Test tenant config validation."""
    result = await mcp_client.call_tool(
        "get_tenant_config",
        {"tenant_id": tenant_id}
    )

    assert result.success == expected_success
```

### 1.7 Dependencies Update

**File**: `pyproject.toml` (additions)

```toml
dependencies = [
    # ... existing dependencies ...
    "fastmcp>=2.13.1",
]

[project.optional-dependencies]
test = [
    # ... existing test dependencies ...
    "pytest-asyncio>=0.21",
    "httpx>=0.27.0",  # For testing HTTP transport
]

[tool.pytest.ini_options]
asyncio_mode = "auto"  # Enable async test support
```

### 1.8 Local Testing with Claude Desktop

**File**: `~/.config/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows)

```json
{
  "mcpServers": {
    "paidsocialnav": {
      "command": "python",
      "args": [
        "-m",
        "mcp_server.server"
      ],
      "cwd": "/Users/robertwelborn/PycharmProjects/PaidSocialNav",
      "env": {
        "GCP_PROJECT_ID": "your-project",
        "META_ACCESS_TOKEN": "your-token",
        "ANTHROPIC_API_KEY": "your-key"
      }
    }
  }
}
```

### Success Criteria for Phase 1

- ✅ MCP server runs locally with `python -m mcp_server.server`
- ✅ All 4 tools are registered and callable
- ✅ All 4 resources are registered and accessible
- ✅ All 3 prompts are registered
- ✅ Tests pass with `pytest tests/test_mcp_server.py`
- ✅ Claude Desktop can connect and list tools
- ✅ At least one end-to-end workflow works (e.g., get_tenant_config)

---

## Phase 2: Remote Deployment to Cloud Run

**Goal**: Deploy MCP server to Google Cloud Run with OAuth authentication

**Duration**: 2-3 days

**Deliverables**:
- Dockerfile for containerized deployment
- Cloud Run deployment configuration
- Google OAuth authentication
- Production environment configuration
- Deployment scripts and documentation

### 2.1 Dockerfile

**File**: `Dockerfile`

```dockerfile
FROM python:3.13-slim

# Copy uv binary for fast dependency installation
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml ./
COPY paid_social_nav/ ./paid_social_nav/
COPY mcp_server/ ./mcp_server/
COPY configs/ ./configs/
COPY sql/ ./sql/

# Install dependencies
RUN uv pip install --system -e .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV MCP_TRANSPORT=http
ENV PORT=8080

# Expose port
EXPOSE 8080

# Run server
CMD ["python", "-m", "mcp_server.server"]
```

### 2.2 Authentication Setup

**File**: `mcp_server/auth.py`

```python
"""Authentication providers for PaidSocialNav MCP server."""
from fastmcp.server.auth.providers.google import GoogleProvider
from fastmcp.server.auth.providers.jwt import JWTVerifier
import os

def get_auth_provider():
    """
    Get authentication provider based on environment configuration.

    Supports:
    - Google OAuth (recommended for Cloud Run)
    - JWT verification (for custom auth systems)
    - None (for local development only)
    """
    auth_type = os.environ.get("MCP_AUTH_TYPE", "none")

    if auth_type == "google":
        return GoogleProvider(
            client_id=os.environ["GOOGLE_CLIENT_ID"],
            client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
            base_url=os.environ["MCP_BASE_URL"]
        )

    elif auth_type == "jwt":
        return JWTVerifier(
            jwks_uri=os.environ["JWT_JWKS_URI"],
            issuer=os.environ["JWT_ISSUER"],
            audience=os.environ["JWT_AUDIENCE"]
        )

    elif auth_type == "none":
        # Local development only - NO AUTHENTICATION
        return None

    else:
        raise ValueError(f"Unknown auth type: {auth_type}")
```

**Update** `mcp_server/server.py`:

```python
from mcp_server.auth import get_auth_provider

# Create authenticated server
auth = get_auth_provider()

mcp = FastMCP(
    "PaidSocialNav",
    version="0.1.0",
    description="Paid social media advertising audit and analytics platform",
    auth=auth  # Add authentication
)
```

### 2.3 Deployment Configuration

**File**: `.env.production.example`

```bash
# GCP Configuration
GCP_PROJECT_ID=your-gcp-project
GCP_REGION=us-central1
CLOUD_RUN_SERVICE_NAME=paidsocialnav-mcp

# MCP Server Configuration
MCP_TRANSPORT=http
PORT=8080
MCP_BASE_URL=https://paidsocialnav-mcp-xxxxx-uc.a.run.app

# Authentication
MCP_AUTH_TYPE=google
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-xxxxx

# PaidSocialNav Configuration
META_ACCESS_TOKEN=secret://projects/PROJECT_ID/secrets/META_ACCESS_TOKEN
ANTHROPIC_API_KEY=secret://projects/PROJECT_ID/secrets/ANTHROPIC_API_KEY
BQ_DATASET=paid_social

# Google Services
GOOGLE_APPLICATION_CREDENTIALS=/app/service-account.json
```

### 2.4 Deployment Scripts

**File**: `scripts/deploy_cloud_run.sh`

```bash
#!/bin/bash
set -e

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-your-project-id}"
REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="paidsocialnav-mcp"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo "🚀 Deploying PaidSocialNav MCP Server to Cloud Run"
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Service: $SERVICE_NAME"

# Build container image
echo "📦 Building container image..."
gcloud builds submit \
  --tag="${IMAGE_NAME}" \
  --project="${PROJECT_ID}"

# Deploy to Cloud Run
echo "🌐 Deploying to Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
  --image="${IMAGE_NAME}" \
  --platform=managed \
  --region="${REGION}" \
  --no-allow-unauthenticated \
  --service-account=paidsocialnav-sa@${PROJECT_ID}.iam.gserviceaccount.com \
  --set-env-vars="MCP_TRANSPORT=http" \
  --set-env-vars="MCP_AUTH_TYPE=google" \
  --set-secrets="META_ACCESS_TOKEN=META_ACCESS_TOKEN:latest" \
  --set-secrets="ANTHROPIC_API_KEY=ANTHROPIC_API_KEY:latest" \
  --set-secrets="GOOGLE_CLIENT_SECRET=MCP_GOOGLE_CLIENT_SECRET:latest" \
  --memory=2Gi \
  --cpu=2 \
  --timeout=300 \
  --concurrency=80 \
  --min-instances=0 \
  --max-instances=10 \
  --project="${PROJECT_ID}"

# Get service URL
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" \
  --platform=managed \
  --region="${REGION}" \
  --format='value(status.url)' \
  --project="${PROJECT_ID}")

echo "✅ Deployment complete!"
echo "Service URL: ${SERVICE_URL}"
echo "MCP Endpoint: ${SERVICE_URL}/mcp"
echo ""
echo "To test the deployment:"
echo "  gcloud run services proxy ${SERVICE_NAME} --region=${REGION}"
echo "  Then connect to http://localhost:8080/mcp"
```

### 2.5 Infrastructure Setup

**File**: `scripts/setup_cloud_infrastructure.sh`

```bash
#!/bin/bash
set -e

PROJECT_ID="${GCP_PROJECT_ID}"
REGION="${GCP_REGION:-us-central1}"

echo "🔧 Setting up Cloud infrastructure for PaidSocialNav MCP"

# Enable required APIs
echo "Enabling required Google Cloud APIs..."
gcloud services enable \
  run.googleapis.com \
  secretmanager.googleapis.com \
  bigquery.googleapis.com \
  storage-api.googleapis.com \
  --project="${PROJECT_ID}"

# Create service account
echo "Creating service account..."
gcloud iam service-accounts create paidsocialnav-sa \
  --display-name="PaidSocialNav MCP Server" \
  --project="${PROJECT_ID}" || true

SA_EMAIL="paidsocialnav-sa@${PROJECT_ID}.iam.gserviceaccount.com"

# Grant necessary permissions
echo "Granting IAM permissions..."
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/bigquery.dataEditor"

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/bigquery.jobUser"

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/storage.objectAdmin"

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/secretmanager.secretAccessor"

# Create secrets (if they don't exist)
echo "Creating secrets..."
echo -n "placeholder" | gcloud secrets create META_ACCESS_TOKEN \
  --data-file=- \
  --replication-policy="automatic" \
  --project="${PROJECT_ID}" || true

echo -n "placeholder" | gcloud secrets create ANTHROPIC_API_KEY \
  --data-file=- \
  --replication-policy="automatic" \
  --project="${PROJECT_ID}" || true

echo -n "placeholder" | gcloud secrets create MCP_GOOGLE_CLIENT_SECRET \
  --data-file=- \
  --replication-policy="automatic" \
  --project="${PROJECT_ID}" || true

echo "✅ Infrastructure setup complete!"
echo ""
echo "⚠️  IMPORTANT: Update the following secrets with actual values:"
echo "  gcloud secrets versions add META_ACCESS_TOKEN --data-file=- --project=${PROJECT_ID}"
echo "  gcloud secrets versions add ANTHROPIC_API_KEY --data-file=- --project=${PROJECT_ID}"
echo "  gcloud secrets versions add MCP_GOOGLE_CLIENT_SECRET --data-file=- --project=${PROJECT_ID}"
```

### 2.6 Testing Remote Deployment

**File**: `scripts/test_remote_mcp.py`

```python
"""Test remote MCP server deployment."""
import asyncio
from fastmcp import Client
import os

async def test_remote_server():
    """Test the deployed MCP server."""
    # Use authenticated proxy: gcloud run services proxy paidsocialnav-mcp
    server_url = os.environ.get("MCP_SERVER_URL", "http://localhost:8080/mcp")

    print(f"Connecting to MCP server at {server_url}")

    async with Client(server_url) as client:
        # Test tool listing
        print("\n📋 Testing tool listing...")
        tools = await client.list_tools()
        print(f"Available tools: {[t.name for t in tools]}")

        # Test resource listing
        print("\n📚 Testing resource listing...")
        resources = await client.list_resources()
        print(f"Available resources: {len(resources)} resources")

        # Test tenant config
        print("\n🏢 Testing get_tenant_config...")
        result = await client.call_tool(
            "get_tenant_config",
            {"tenant_id": "puttery"}
        )
        print(f"Result: {result}")

        # Test tenant list resource
        print("\n👥 Testing tenant list resource...")
        tenant_data = await client.read_resource("tenants://list")
        print(f"Tenants: {tenant_data[0].text[:200]}...")

        print("\n✅ All tests passed!")

if __name__ == "__main__":
    asyncio.run(test_remote_server())
```

### Success Criteria for Phase 2

- ✅ Container builds successfully with `gcloud builds submit`
- ✅ Service deploys to Cloud Run without errors
- ✅ Health check endpoint `/health` returns 200 OK
- ✅ Google OAuth authentication is configured and working
- ✅ Service scales from 0 to 1+ instances on first request
- ✅ All secrets are properly mounted from Secret Manager
- ✅ Authenticated proxy allows MCP client connection
- ✅ End-to-end test script passes against deployed service
- ✅ Logging shows structured logs in Cloud Logging

---

## Phase 3: Production Hardening

**Goal**: Add monitoring, error handling, rate limiting, and operational tooling

**Duration**: 2-3 days

**Deliverables**:
- Comprehensive error handling and logging
- Rate limiting and quota management
- Monitoring dashboards and alerts
- Operational runbook
- Performance optimization

### 3.1 Enhanced Error Handling

**File**: `mcp_server/error_handling.py`

```python
"""Centralized error handling for MCP server."""
from fastmcp import Context
from paid_social_nav.core.logging_config import get_logger
import traceback

logger = get_logger(__name__)

class MCPError(Exception):
    """Base exception for MCP server errors."""
    pass

class AuthenticationError(MCPError):
    """Authentication failed."""
    pass

class ValidationError(MCPError):
    """Input validation failed."""
    pass

class ResourceNotFoundError(MCPError):
    """Requested resource not found."""
    pass

class ExternalServiceError(MCPError):
    """External service (BigQuery, Meta API) failed."""
    pass


async def handle_tool_error(
    error: Exception,
    tool_name: str,
    ctx: Context | None = None
) -> dict:
    """
    Standardized error handling for MCP tools.

    Args:
        error: The exception that occurred
        tool_name: Name of the tool that failed
        ctx: MCP context for client logging

    Returns:
        Standardized error response dict
    """
    # Log full error server-side
    logger.exception(f"Error in tool '{tool_name}': {str(error)}")

    # Determine error type and client message
    if isinstance(error, ValidationError):
        error_type = "validation_error"
        client_message = str(error)
    elif isinstance(error, ResourceNotFoundError):
        error_type = "not_found"
        client_message = str(error)
    elif isinstance(error, ExternalServiceError):
        error_type = "external_service_error"
        client_message = "External service temporarily unavailable. Please try again."
    elif isinstance(error, AuthenticationError):
        error_type = "authentication_error"
        client_message = "Authentication failed. Check credentials."
    else:
        error_type = "internal_error"
        client_message = "An unexpected error occurred. Please contact support."

    # Send sanitized error to client
    if ctx:
        await ctx.error(f"{tool_name} failed: {client_message}")

    return {
        "success": False,
        "error_type": error_type,
        "message": client_message,
        "tool": tool_name
    }
```

### 3.2 Rate Limiting

**File**: `mcp_server/rate_limiting.py`

```python
"""Rate limiting for MCP server."""
from collections import defaultdict
from datetime import datetime, timedelta
import asyncio

class RateLimiter:
    """
    Token bucket rate limiter.

    Limits requests per tenant to prevent abuse.
    """

    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.buckets = defaultdict(lambda: {
            "tokens": requests_per_minute,
            "last_update": datetime.now()
        })

    async def check_limit(self, tenant_id: str) -> tuple[bool, str]:
        """
        Check if request is within rate limit.

        Returns:
            (allowed, message) tuple
        """
        bucket = self.buckets[tenant_id]
        now = datetime.now()

        # Refill tokens based on time elapsed
        elapsed = (now - bucket["last_update"]).total_seconds()
        tokens_to_add = elapsed * (self.requests_per_minute / 60)
        bucket["tokens"] = min(
            self.requests_per_minute,
            bucket["tokens"] + tokens_to_add
        )
        bucket["last_update"] = now

        # Check if request allowed
        if bucket["tokens"] >= 1:
            bucket["tokens"] -= 1
            return True, ""
        else:
            retry_after = int((1 - bucket["tokens"]) * 60 / self.requests_per_minute)
            return False, f"Rate limit exceeded. Retry after {retry_after} seconds."


# Global rate limiter instance
rate_limiter = RateLimiter(requests_per_minute=60)
```

### 3.3 Monitoring Setup

**File**: `mcp_server/monitoring.py`

```python
"""Monitoring and metrics for MCP server."""
from paid_social_nav.core.logging_config import get_logger
from datetime import datetime
from typing import Any
import time

logger = get_logger(__name__)

class MetricsCollector:
    """Collect metrics for monitoring."""

    def __init__(self):
        self.tool_calls = {}
        self.errors = {}
        self.latencies = {}

    def record_tool_call(self, tool_name: str, duration: float, success: bool):
        """Record tool call metrics."""
        if tool_name not in self.tool_calls:
            self.tool_calls[tool_name] = {"total": 0, "success": 0, "failure": 0}

        self.tool_calls[tool_name]["total"] += 1
        if success:
            self.tool_calls[tool_name]["success"] += 1
        else:
            self.tool_calls[tool_name]["failure"] += 1

        # Record latency
        if tool_name not in self.latencies:
            self.latencies[tool_name] = []
        self.latencies[tool_name].append(duration)

    def record_error(self, error_type: str, tool_name: str):
        """Record error metrics."""
        key = f"{tool_name}:{error_type}"
        self.errors[key] = self.errors.get(key, 0) + 1

    def get_metrics(self) -> dict[str, Any]:
        """Get current metrics snapshot."""
        return {
            "timestamp": datetime.now().isoformat(),
            "tool_calls": self.tool_calls,
            "errors": self.errors,
            "latencies": {
                tool: {
                    "avg": sum(times) / len(times),
                    "max": max(times),
                    "min": min(times),
                    "count": len(times)
                }
                for tool, times in self.latencies.items()
            }
        }


# Global metrics collector
metrics = MetricsCollector()


def track_tool_execution(func):
    """Decorator to track tool execution metrics."""
    async def wrapper(*args, **kwargs):
        start = time.time()
        success = False

        try:
            result = await func(*args, **kwargs)
            success = result.get("success", False)
            return result
        except Exception as e:
            logger.exception(f"Tool {func.__name__} failed")
            raise
        finally:
            duration = time.time() - start
            metrics.record_tool_call(func.__name__, duration, success)

    return wrapper
```

**Add metrics endpoint to** `mcp_server/server.py`:

```python
from mcp_server.monitoring import metrics

@mcp.custom_route("/metrics", methods=["GET"])
def get_metrics():
    """Metrics endpoint for monitoring."""
    return metrics.get_metrics()
```

### 3.4 Operational Runbook

**File**: `docs/RUNBOOK.md`

```markdown
# PaidSocialNav MCP Server Operational Runbook

## Service Overview

- **Service Name**: paidsocialnav-mcp
- **Platform**: Google Cloud Run
- **Region**: us-central1
- **Repository**: datablogin/PaidSocialNav

## Health Checks

### Service Health
```bash
curl https://paidsocialnav-mcp-xxxxx-uc.a.run.app/health
# Expected: {"status": "healthy", "service": "PaidSocialNav MCP Server"}
```

### Metrics
```bash
curl https://paidsocialnav-mcp-xxxxx-uc.a.run.app/metrics
# Returns tool call counts, error rates, latencies
```

## Common Issues

### Issue: Service not responding
**Symptoms**: HTTP 502/503 errors, timeouts

**Diagnosis**:
```bash
# Check service status
gcloud run services describe paidsocialnav-mcp --region=us-central1

# Check recent logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=paidsocialnav-mcp" --limit=50
```

**Resolution**:
1. Check if service scaled to zero (normal behavior)
2. Check for startup errors in logs
3. Verify environment variables and secrets are set
4. Redeploy if necessary: `bash scripts/deploy_cloud_run.sh`

### Issue: Authentication failures
**Symptoms**: 401 Unauthorized errors

**Diagnosis**:
```bash
# Verify OAuth configuration
gcloud secrets versions access latest --secret=MCP_GOOGLE_CLIENT_SECRET
```

**Resolution**:
1. Verify Google OAuth client ID and secret are correct
2. Check that redirect URLs are configured in Google Cloud Console
3. Ensure service account has necessary permissions

### Issue: BigQuery errors
**Symptoms**: "External service error" in tool responses

**Diagnosis**:
```bash
# Check service account permissions
gcloud projects get-iam-policy PROJECT_ID --flatten="bindings[].members" --filter="bindings.members:paidsocialnav-sa@*"
```

**Resolution**:
1. Verify service account has `bigquery.dataEditor` and `bigquery.jobUser` roles
2. Check BigQuery quotas haven't been exceeded
3. Verify dataset exists and is accessible

## Deployment

### Standard Deployment
```bash
cd /path/to/PaidSocialNav
bash scripts/deploy_cloud_run.sh
```

### Rollback to Previous Version
```bash
# List revisions
gcloud run revisions list --service=paidsocialnav-mcp --region=us-central1

# Route 100% traffic to specific revision
gcloud run services update-traffic paidsocialnav-mcp \
  --to-revisions=paidsocialnav-mcp-00042=100 \
  --region=us-central1
```

### Update Secrets
```bash
# Update Meta access token
echo -n "new-token-value" | gcloud secrets versions add META_ACCESS_TOKEN --data-file=-

# Update Anthropic API key
echo -n "new-key-value" | gcloud secrets versions add ANTHROPIC_API_KEY --data-file=-
```

## Monitoring

### Key Metrics to Watch
- **Request count**: Should scale with usage
- **Error rate**: Should stay <1%
- **Latency p95**: Should be <5s for audit_workflow, <1s for other tools
- **Container CPU**: Should stay <80%
- **Container memory**: Should stay <1.5GB

### Setting Up Alerts
```bash
# Create alert policy for error rate
gcloud alpha monitoring policies create \
  --notification-channels=CHANNEL_ID \
  --display-name="PaidSocialNav MCP High Error Rate" \
  --condition-display-name="Error rate > 5%" \
  --condition-threshold-value=0.05 \
  --condition-threshold-duration=300s
```

## Scaling Configuration

Current settings:
- Min instances: 0 (scale to zero)
- Max instances: 10
- Concurrency: 80 requests per instance
- Memory: 2Gi
- CPU: 2

To adjust:
```bash
gcloud run services update paidsocialnav-mcp \
  --min-instances=1 \
  --max-instances=20 \
  --region=us-central1
```

## Useful Commands

### View Recent Logs
```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=paidsocialnav-mcp" \
  --limit=100 \
  --format=json
```

### Tail Logs in Real-Time
```bash
gcloud logging tail "resource.type=cloud_run_revision AND resource.labels.service_name=paidsocialnav-mcp"
```

### Test with Authenticated Proxy
```bash
gcloud run services proxy paidsocialnav-mcp --region=us-central1
# Server accessible at http://localhost:8080
```

### Get Service URL
```bash
gcloud run services describe paidsocialnav-mcp \
  --region=us-central1 \
  --format='value(status.url)'
```

## Emergency Contacts

- **Primary**: Robert Welborn (robert@example.com)
- **On-call**: [On-call schedule link]
- **GCP Support**: [Support case link]
```

### Success Criteria for Phase 3

- ✅ Error handling provides clear, actionable messages to clients
- ✅ Rate limiting prevents abuse (60 requests/minute per tenant)
- ✅ Metrics endpoint exposes key performance indicators
- ✅ Cloud Logging captures structured logs for debugging
- ✅ Monitoring dashboard shows request volume, latency, errors
- ✅ Alerts configured for high error rates and latency
- ✅ Runbook covers common operational scenarios
- ✅ Load testing shows service handles 10+ concurrent requests
- ✅ Service scales from 0 to multiple instances automatically

---

## Phase 4: Documentation & Handoff

**Goal**: Complete documentation for users and maintainers

**Duration**: 1 day

**Deliverables**:
- User guide for connecting MCP clients
- API reference documentation
- Architecture diagrams
- Contribution guidelines
- Security and compliance documentation

### 4.1 User Guide

**File**: `docs/MCP_USER_GUIDE.md`

```markdown
# PaidSocialNav MCP Server User Guide

## Introduction

The PaidSocialNav MCP Server exposes paid social media advertising audit capabilities through the Model Context Protocol (MCP), enabling AI assistants like Claude to access analytics and reporting tools via natural language conversation.

## Getting Started

### Prerequisites

- Google Cloud account with access to paidsocialnav-mcp service
- MCP-compatible client (Claude Desktop, Claude API, or custom MCP client)
- BigQuery dataset with Meta advertising data

### Connecting to the Server

#### Option 1: Via Claude Desktop

1. Install Claude Desktop (version 0.7.0 or higher)
2. Open Claude Desktop settings
3. Navigate to "Developer" → "MCP Servers"
4. Add server configuration:

```json
{
  "paidsocialnav": {
    "url": "https://paidsocialnav-mcp-xxxxx-uc.a.run.app/mcp",
    "transport": "http"
  }
}
```

5. Restart Claude Desktop
6. Server tools will appear automatically in conversations

#### Option 2: Via Authenticated Proxy (Recommended for Testing)

```bash
# Start authenticated proxy
gcloud run services proxy paidsocialnav-mcp --region=us-central1

# Connect to http://localhost:8080/mcp
```

#### Option 3: Via Python FastMCP Client

```python
from fastmcp import Client
import asyncio

async def main():
    async with Client("https://paidsocialnav-mcp-xxxxx-uc.a.run.app/mcp") as client:
        # List available tools
        tools = await client.list_tools()
        print([t.name for t in tools])

        # Call a tool
        result = await client.call_tool(
            "get_tenant_config",
            {"tenant_id": "puttery"}
        )
        print(result)

asyncio.run(main())
```

## Available Tools

### meta_sync_insights

Synchronize Meta advertising insights to BigQuery.

**Parameters**:
- `account_id` (required): Meta ad account ID (e.g., "act_123456789")
- `level` (optional): Aggregation level (ad, adset, or campaign), default: "ad"
- `date_preset` (optional): Named date range (yesterday, last_7d, last_28d, etc.)
- `since` (optional): Start date (YYYY-MM-DD)
- `until` (optional): End date (YYYY-MM-DD)
- `tenant` (optional): Tenant ID from configs/tenants.yaml

**Example**:
```
Sync Meta insights for account act_123456789 for the last 7 days at campaign level.
```

### audit_workflow

Run complete audit analysis with reports and optional AI insights.

**Parameters**:
- `tenant_id` (required): Tenant identifier
- `audit_config` (required): Path to audit YAML configuration
- `output_dir` (optional): Output directory, default: "reports/"
- `formats` (optional): Comma-separated formats (md, html, pdf), default: "md,html,pdf"
- `sheets_export` (optional): Export to Google Sheets, default: false

**Example**:
```
Run audit for puttery tenant using configs/audit_puttery.yaml and export to Google Sheets.
```

### get_tenant_config

Retrieve tenant configuration details.

**Parameters**:
- `tenant_id` (required): Tenant identifier

**Example**:
```
What's the configuration for the puttery tenant?
```

### load_benchmarks

Load industry benchmark data from CSV into BigQuery.

**Parameters**:
- `project_id` (required): GCP project ID
- `dataset` (required): BigQuery dataset name
- `csv_path` (required): Path to benchmarks CSV file

**Example**:
```
Load benchmarks from benchmarks/retail_us_2024.csv into puttery-golf-001.paid_social.
```

## Available Resources

### tenants://list

List all configured tenants.

**Example**:
```
Show me all available tenants.
```

### audit://results/{tenant_id}/{date}

Retrieve audit results for a specific date.

**Example**:
```
Get audit results for puttery tenant on 2025-01-23.
```

### insights://campaigns/{tenant_id}/{window}

Retrieve campaign insights for a time window.

**Parameters**:
- `tenant_id`: Tenant identifier
- `window`: Time window (last_7d, last_14d, last_28d, last_30d)

**Example**:
```
Show me campaign performance for puttery over the last 28 days.
```

### benchmarks://{industry}/{region}/{spend_band}

Retrieve industry benchmark data.

**Parameters**:
- `industry`: Industry category (retail, finance, etc.)
- `region`: Geographic region (US, EU, etc.)
- `spend_band`: Spend range (10k-50k, 50k-100k, etc.)

**Example**:
```
What are the retail benchmarks for US advertisers spending 10k-50k?
```

## Available Prompts

### analyze_campaign_performance

Generate strategic insights from audit results.

**Example**:
```
Analyze campaign performance and provide strategic recommendations.
```

### audit_setup_wizard

Interactive guide for setting up audit configuration.

**Example**:
```
Help me set up a new audit for a retail client.
```

### data_sync_planner

Plan data synchronization strategy.

**Example**:
```
Plan a sync strategy for a new account with $5000 daily spend.
```

## Common Workflows

### Complete Audit Workflow

```
1. First, sync the latest data:
   "Sync Meta insights for account act_123456789 for the last 28 days"

2. Run the audit:
   "Run audit for puttery using configs/audit_puttery.yaml and export to Sheets"

3. Analyze results:
   "Analyze the campaign performance and provide strategic recommendations"
```

### Data Exploration

```
1. List tenants:
   "Show me all available tenants"

2. Check configuration:
   "What's the configuration for the puttery tenant?"

3. View recent insights:
   "Show me campaign performance for puttery over the last 7 days"

4. Compare to benchmarks:
   "What are the retail benchmarks for US advertisers spending 10k-50k?"
```

## Troubleshooting

### "Authentication failed"
- Verify you have access to the Cloud Run service
- Check that your proxy is running if using local proxy method
- Ensure Google Cloud credentials are configured

### "External service error"
- Check BigQuery dataset exists and is accessible
- Verify Meta API access token is valid
- Check service account permissions

### "Rate limit exceeded"
- Wait 60 seconds and retry
- Reduce request frequency
- Contact administrator to increase limits

## Support

For issues or questions:
- Check the [Runbook](RUNBOOK.md) for operational guidance
- Review logs in Google Cloud Logging
- Contact: robert@example.com
```

### 4.2 API Reference

**File**: `docs/MCP_API_REFERENCE.md`

[Content would include detailed API documentation for all tools, resources, and prompts with parameter schemas, return types, and examples]

### 4.3 Architecture Diagram

**File**: `docs/ARCHITECTURE.md`

[Content would include detailed architecture diagrams, component descriptions, data flow diagrams, and security model]

### Success Criteria for Phase 4

- ✅ User guide covers all common use cases
- ✅ API reference documents all tools, resources, and prompts
- ✅ Architecture diagrams clearly show system design
- ✅ Documentation includes troubleshooting section
- ✅ Security and compliance documentation complete
- ✅ README.md updated with MCP server information
- ✅ All documentation reviewed and approved

---

## Implementation Timeline

| Phase | Duration | Key Milestones |
|-------|----------|----------------|
| **Phase 1: Local Server** | 1-2 days | STDIO server running, tests passing, Claude Desktop integration |
| **Phase 2: Cloud Run** | 2-3 days | Deployed to Cloud Run, OAuth working, remote testing complete |
| **Phase 3: Hardening** | 2-3 days | Monitoring, rate limiting, error handling, runbook complete |
| **Phase 4: Documentation** | 1 day | User guide, API docs, architecture docs complete |
| **Total** | **6-9 days** | Production-ready MCP server deployed and documented |

## Risk Mitigation

### Risk: Breaking existing CLI functionality
**Mitigation**: MCP server imports from core packages without modification. Core packages remain unchanged and independently testable.

### Risk: Authentication complexity
**Mitigation**: Use Google OAuth provider with FastMCP's built-in support. Fallback to authenticated proxy for testing.

### Risk: BigQuery cost overruns
**Mitigation**: Implement rate limiting (60 req/min), add query result caching, monitor query costs in Cloud Billing.

### Risk: MCP protocol changes
**Mitigation**: Use FastMCP library which abstracts protocol details. Pin FastMCP version in production, test upgrades in staging.

### Risk: Service unavailability
**Mitigation**: Cloud Run provides 99.95% SLA, auto-scaling, and health checks. Implement retry logic in clients.

## Success Metrics

### Technical Metrics
- Server startup time < 5 seconds
- Tool execution latency p95 < 5 seconds
- Error rate < 1%
- Test coverage > 80%
- Zero security vulnerabilities

### Business Metrics
- Number of active MCP clients
- Tool call volume per week
- User satisfaction (survey-based)
- Cost per audit request < $0.05

## Next Steps After Implementation

1. **Week 1-2**: Monitor production usage, fix any issues
2. **Month 1**: Collect user feedback, iterate on UX
3. **Month 2**: Add more tools (Reddit, Pinterest, TikTok adapters)
4. **Month 3**: Implement advanced features (scheduled audits, alerts, dashboards)
5. **Ongoing**: Regular security updates, performance optimization, feature enhancements

## Related Documentation

- [FastMCP Documentation](https://gofastmcp.com/)
- [Model Context Protocol Specification](https://modelcontextprotocol.io/)
- [Google Cloud Run Documentation](https://cloud.google.com/run/docs)
- [PaidSocialNav Core Documentation](../README.md)
- [Architecture Evaluation Research](../thoughts/shared/research/2025-11-22-claude-skills-mcp-architecture-evaluation.md)

---

**Document Status**: Draft
**Last Updated**: 2025-11-23
**Next Review**: After Phase 1 completion
