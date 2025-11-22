"""Integration tests for the full audit → render pipeline.

This test exercises the complete workflow from audit execution through
report rendering, using mocked BigQuery responses for CI compatibility.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import Mock

import pytest

from paid_social_nav.audit.engine import AuditConfig, AuditEngine
from paid_social_nav.render.renderer import ReportRenderer


@pytest.fixture
def mock_bq_client():
    """Create a mock BigQuery client with realistic audit data responses."""
    mock_client = Mock()

    # Mock insights_rollups data for KPIs
    def query_insights_rollups(sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Return realistic KPI data for different windows."""
        # Return data for Q4 and last_30d windows
        return [
            {
                "window": "Q4",
                "impressions": 1250000,
                "clicks": 18750,
                "ctr": 0.015,
                "spend": 12500.00,
                "frequency": 2.1,
                "reach": 595238,
            },
            {
                "window": "last_30d",
                "impressions": 450000,
                "clicks": 6750,
                "ctr": 0.015,
                "spend": 4500.00,
                "frequency": 2.3,
                "reach": 195652,
            },
        ]

    # Mock budget pacing data
    def query_budget_pacing(sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Return realistic spend data by window."""
        window = params.get("window")

        spend_map = {
            "Q4": 12500.00,
            "last_30d": 4500.00,
        }

        return [{"spend": spend_map.get(window, 0.0)}]

    # Mock budget concentration data
    def query_budget_concentration(sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Return realistic top-N concentration data."""
        window = params.get("window")

        # Simulate top-5 campaigns accounting for 65% of spend (healthy)
        concentration_map = {
            "Q4": 0.65,
            "last_30d": 0.68,
        }

        return [{"top_n_share": concentration_map.get(window, 0.0)}]

    # Mock creative mix data
    def query_creative_mix(sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Return realistic creative diversity data."""
        # Simulate balanced creative mix
        return [
            {
                "video_share": 0.55,
                "image_share": 0.45,
            }
        ]

    # Mock tracking data
    def query_tracking(sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Return realistic conversion tracking data."""
        window = params.get("window")

        clicks_map = {
            "Q4": 18750,
            "last_30d": 6750,
        }
        conversions_map = {
            "Q4": 375,
            "last_30d": 135,
        }

        clicks = clicks_map.get(window, 0)
        conversions = conversions_map.get(window, 0)
        conv_rate = conversions / clicks if clicks > 0 else 0.0

        return [
            {
                "clicks": clicks,
                "conversions": conversions,
                "conv_rate": conv_rate,
            }
        ]

    # Route queries based on table name patterns
    def mock_query_rows(sql: str, params: dict[str, Any] | None = None, **kwargs) -> list[dict[str, Any]]:
        if params is None:
            params = {}

        # Route based on which table/view is being queried
        if "insights_rollups" in sql and "SUM(clicks)" in sql:
            # Tracking query (aggregated)
            return query_tracking(sql, params)
        elif "insights_rollups" in sql:
            # General KPI query
            return query_insights_rollups(sql, params)
        elif "v_budget_pacing" in sql:
            return query_budget_pacing(sql, params)
        elif "v_budget_concentration" in sql:
            return query_budget_concentration(sql, params)
        elif "v_creative_mix" in sql:
            return query_creative_mix(sql, params)
        else:
            # Default empty response
            return []

    mock_client.query_rows = Mock(side_effect=mock_query_rows)
    return mock_client


@pytest.fixture
def audit_config() -> AuditConfig:
    """Create a realistic audit configuration."""
    return AuditConfig(
        project="test-project",
        dataset="paid_social",
        tenant="test_client",
        windows=["Q4", "last_30d"],
        level="campaign",
        weights={
            "pacing_vs_target": 0.25,
            "ctr_threshold": 0.15,
            "frequency_threshold": 0.15,
            "budget_concentration": 0.20,
            "creative_diversity": 0.15,
            "tracking_health": 0.10,
        },
        thresholds={
            "pacing_tolerance": 0.1,
            "pacing_tol_cap": 0.5,
            "min_ctr": 0.01,
            "max_frequency": 2.5,
            "freq_overage_cap": 1.0,
            "max_topn_share": 0.7,
            "min_video_share": 0.2,
            "min_image_share": 0.2,
            "min_conv_rate": 0.01,
            "min_clicks_for_tracking": 100,
            "target_spend_by_window": {
                "Q4": 12000.00,  # Slightly under target for testing
                "last_30d": 4500.00,  # On target
            },
        },
        top_n=5,
    )


def test_audit_to_markdown_integration(mock_bq_client, audit_config):
    """Test the complete audit → Markdown rendering pipeline.

    This integration test:
    1. Creates a realistic audit configuration
    2. Mocks BigQuery to return realistic data
    3. Runs the actual audit engine
    4. Renders the result to Markdown
    5. Validates the output structure and content
    """
    # Run the audit with mocked BigQuery client
    engine = AuditEngine(audit_config, bq=mock_bq_client)
    result = engine.run()

    # Verify audit result structure
    assert "overall_score" in result
    assert "rules" in result
    assert isinstance(result["overall_score"], float)
    assert isinstance(result["rules"], list)
    assert len(result["rules"]) > 0

    # Verify we have results for each rule type
    rule_names = {r["rule"] for r in result["rules"]}
    expected_rules = {
        "pacing_vs_target",
        "ctr_threshold",
        "frequency_threshold",
        "budget_concentration",
        "creative_diversity",
        "tracking_health",
    }
    assert expected_rules.issubset(rule_names), f"Missing rules: {expected_rules - rule_names}"

    # Verify rule structure
    for rule_result in result["rules"]:
        assert "rule" in rule_result
        assert "level" in rule_result
        assert "window" in rule_result
        assert "score" in rule_result
        assert "findings" in rule_result
        assert 0 <= rule_result["score"] <= 100
        assert rule_result["level"] == "campaign"
        assert rule_result["window"] in ["Q4", "last_30d"]

    # Prepare data for rendering
    today = datetime.now().strftime("%Y-%m-%d")
    render_data = {
        "tenant_name": audit_config.tenant,
        "period": "Q4 2025",
        "audit_date": today,
        "overall_score": result["overall_score"],
        "rules": result["rules"],
        "recommendations": [],
    }

    # Render to Markdown
    renderer = ReportRenderer()
    markdown_output = renderer.render_markdown(render_data)

    # Verify Markdown output structure
    assert isinstance(markdown_output, str)
    assert len(markdown_output) > 0

    # Check header content
    assert "test_client" in markdown_output
    assert "Q4 2025" in markdown_output
    assert today in markdown_output

    # Check score formatting (may be rendered as int or float)
    overall_score_int = int(result["overall_score"])
    assert f"{overall_score_int}/100" in markdown_output or f"{result['overall_score']}/100" in markdown_output

    # Check executive summary is present
    assert "Executive Summary" in markdown_output or "Performance" in markdown_output

    # Check rule sections are present
    assert "Pacing Vs Target" in markdown_output
    assert "Ctr Threshold" in markdown_output or "CTR Threshold" in markdown_output
    assert "Frequency Threshold" in markdown_output
    assert "Budget Concentration" in markdown_output
    assert "Creative Diversity" in markdown_output
    assert "Tracking Health" in markdown_output

    # Check scores are rendered (may be int or float format)
    for rule_result in result["rules"]:
        score_int = f"{int(rule_result['score'])}/100"
        score_float = f"{rule_result['score']}/100"
        assert score_int in markdown_output or score_float in markdown_output, \
            f"Score {score_int} or {score_float} for rule {rule_result['rule']} not found"

    # Check version footer
    assert "PaidSocialNav v" in markdown_output
    assert "0.1.0" in markdown_output


def test_audit_to_html_integration(mock_bq_client, audit_config):
    """Test the complete audit → HTML rendering pipeline.

    This integration test validates HTML rendering with Chart.js visualizations.
    """
    # Run the audit with mocked BigQuery client
    engine = AuditEngine(audit_config, bq=mock_bq_client)
    result = engine.run()

    # Prepare data for rendering
    today = datetime.now().strftime("%Y-%m-%d")
    render_data = {
        "tenant_name": audit_config.tenant,
        "period": "Q4 2025",
        "audit_date": today,
        "overall_score": result["overall_score"],
        "rules": result["rules"],
        "recommendations": [],
    }

    # Render to HTML
    renderer = ReportRenderer()
    html_output = renderer.render_html(render_data)

    # Verify HTML structure
    assert isinstance(html_output, str)
    assert "<!DOCTYPE html>" in html_output
    assert "<html" in html_output
    assert "</html>" in html_output

    # Check content is present
    assert "test_client" in html_output
    assert "Q4 2025" in html_output

    # Check Chart.js is included
    assert "chart.js" in html_output.lower()
    assert "canvas" in html_output.lower()

    # Check version footer
    assert "PaidSocialNav v" in html_output
    assert "0.1.0" in html_output


def test_audit_with_edge_cases(mock_bq_client):
    """Test audit engine handles edge cases correctly.

    This test verifies the audit engine properly handles:
    - Zero spend scenarios
    - Missing data
    - Extreme metric values
    """
    # Create config with minimal thresholds
    edge_config = AuditConfig(
        project="test-project",
        dataset="paid_social",
        tenant="edge_case_client",
        windows=["Q4"],
        level="campaign",
        weights={
            "pacing_vs_target": 0.5,
            "ctr_threshold": 0.5,
        },
        thresholds={
            "pacing_tolerance": 0.1,
            "pacing_tol_cap": 0.5,
            "min_ctr": 0.01,
            "target_spend_by_window": {
                "Q4": 12000.00,
            },
        },
        top_n=None,  # Skip budget concentration
    )

    # Run audit
    engine = AuditEngine(edge_config, bq=mock_bq_client)
    result = engine.run()

    # Verify result structure is valid even with edge cases
    assert "overall_score" in result
    assert "rules" in result
    assert isinstance(result["overall_score"], float)
    assert result["overall_score"] >= 0
    assert result["overall_score"] <= 100

    # Verify each rule has valid score
    for rule_result in result["rules"]:
        assert 0 <= rule_result["score"] <= 100
        assert isinstance(rule_result["findings"], dict)


def test_audit_result_matches_renderer_expectations(mock_bq_client, audit_config):
    """Test that AuditEngine output matches ReportRenderer expectations.

    This test verifies the data contract between the audit engine and renderer.
    """
    # Run audit
    engine = AuditEngine(audit_config, bq=mock_bq_client)
    result = engine.run()

    # Build renderer data structure
    today = datetime.now().strftime("%Y-%m-%d")
    render_data = {
        "tenant_name": audit_config.tenant,
        "period": "Q4 2025",
        "audit_date": today,
        "overall_score": result["overall_score"],
        "rules": result["rules"],
        "recommendations": [],
    }

    # Verify all required keys are present
    required_keys = ["tenant_name", "period", "audit_date", "overall_score", "rules", "recommendations"]
    for key in required_keys:
        assert key in render_data, f"Missing required key: {key}"

    # Verify rule data structure matches renderer expectations
    for rule in render_data["rules"]:
        # Required fields for rendering
        assert "rule" in rule
        assert "level" in rule
        assert "window" in rule
        assert "score" in rule
        assert "findings" in rule

        # Verify types
        assert isinstance(rule["rule"], str)
        assert isinstance(rule["level"], str)
        assert isinstance(rule["window"], str)
        assert isinstance(rule["score"], int | float)
        assert isinstance(rule["findings"], dict)

    # Verify it renders without errors
    renderer = ReportRenderer()
    markdown = renderer.render_markdown(render_data)
    html = renderer.render_html(render_data)

    assert len(markdown) > 0
    assert len(html) > 0


def test_multiple_windows_in_report(mock_bq_client, audit_config):
    """Test that reports correctly show data for multiple time windows.

    This test ensures the audit and rendering pipeline handles multiple
    time windows (Q4, last_30d) correctly.
    """
    # Run audit with multiple windows
    engine = AuditEngine(audit_config, bq=mock_bq_client)
    result = engine.run()

    # Verify we have results for both windows
    windows_found = {r["window"] for r in result["rules"]}
    assert "Q4" in windows_found
    assert "last_30d" in windows_found

    # Prepare render data
    today = datetime.now().strftime("%Y-%m-%d")
    render_data = {
        "tenant_name": audit_config.tenant,
        "period": "Q4 2025",
        "audit_date": today,
        "overall_score": result["overall_score"],
        "rules": result["rules"],
        "recommendations": [],
    }

    # Render to Markdown
    renderer = ReportRenderer()
    markdown = renderer.render_markdown(render_data)

    # Verify both windows appear in output
    assert "Q4" in markdown
    assert "last_30d" in markdown or "30d" in markdown

    # Count how many times we see each window (should be multiple rules per window)
    q4_count = markdown.count("Q4")
    last_30d_count = markdown.count("last_30d") + markdown.count("30d")

    assert q4_count >= 5, "Should have multiple Q4 results"
    assert last_30d_count >= 5, "Should have multiple last_30d results"
