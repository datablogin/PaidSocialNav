"""MCP prompts for PaidSocialNav workflows."""

from __future__ import annotations

from fastmcp.prompts.prompt import PromptMessage, TextContent


def analyze_campaign_performance_prompt(
    tenant_name: str, overall_score: float, formatted_rules: str
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
        PromptMessage(role="user", content=TextContent(type="text", text=prompt_text))
    ]


def audit_setup_wizard_prompt(
    tenant_name: str,
    project_id: str,
    dataset: str,
    available_windows: list[str],
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
        PromptMessage(role="user", content=TextContent(type="text", text=prompt_text))
    ]


def data_sync_planner_prompt(
    tenant_name: str,
    account_id: str,
    duration: str,
    avg_spend: float,
    windows: list[str],
) -> list[PromptMessage]:
    """
    Plan data synchronization strategy.

    Args:
        tenant_name: Client/tenant name
        account_id: Meta ad account ID
        duration: How long account has been running
        avg_spend: Average daily spend
        windows: Required analysis windows
    """
    prompt_text = f"""Plan a data sync strategy for {tenant_name} Meta account {account_id}.

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

    return [
        PromptMessage(role="user", content=TextContent(type="text", text=prompt_text))
    ]
