"""Tests for the report renderer."""
from __future__ import annotations

import pytest

from paid_social_nav.render.renderer import ReportRenderer


def test_renderer_instantiation():
    """Test that ReportRenderer can be instantiated."""
    renderer = ReportRenderer()
    assert renderer is not None
    assert renderer.env is not None


def test_render_markdown_basic():
    """Test basic Markdown rendering with minimal data."""
    renderer = ReportRenderer()
    data = {
        "tenant_name": "test_client",
        "period": "Q4 2025",
        "audit_date": "2025-11-20",
        "overall_score": 75,
        "rules": [],
        "recommendations": [],
    }

    result = renderer.render_markdown(data)

    assert "test_client" in result
    assert "75/100" in result
    assert "Q4 2025" in result
    assert "2025-11-20" in result


def test_render_markdown_with_rules():
    """Test Markdown rendering with rule data including findings dict."""
    renderer = ReportRenderer()
    data = {
        "tenant_name": "test_client",
        "period": "Q4 2025",
        "audit_date": "2025-11-20",
        "overall_score": 72,
        "rules": [
            {
                "rule": "budget_concentration",
                "window": "Q4",
                "level": "campaign",
                "score": 85,
                "findings": {
                    "top_n_share": 0.68,
                    "max_share": 0.70,
                    "within_limit": True,
                }
            }
        ],
        "recommendations": [],
    }

    result = renderer.render_markdown(data)

    # Check that findings dict is formatted properly
    assert "Budget Concentration" in result
    assert "85/100" in result
    assert "Top N Share: 0.68" in result
    assert "Max Share: 0.7" in result
    assert "Within Limit: True" in result


def test_render_markdown_score_ranges():
    """Test that different score ranges produce correct executive summaries."""
    renderer = ReportRenderer()

    test_cases = [
        (95, "✅ **Excellent Performance**"),
        (75, "⚠️ **Good Performance**"),
        (50, "⚠️ **Moderate Performance**"),
        (30, "🔴 **Needs Attention**"),
    ]

    for score, expected_text in test_cases:
        data = {
            "tenant_name": "test",
            "period": "2025",
            "audit_date": "2025-11-20",
            "overall_score": score,
            "rules": [],
            "recommendations": [],
        }
        result = renderer.render_markdown(data)
        assert expected_text in result, f"Score {score} should show: {expected_text}"


def test_render_html_raises_not_implemented():
    """Test that render_html raises NotImplementedError in Phase 1."""
    renderer = ReportRenderer()
    data = {
        "tenant_name": "test",
        "period": "2025",
        "audit_date": "2025-11-20",
        "overall_score": 75,
        "rules": [],
        "recommendations": [],
    }

    with pytest.raises(NotImplementedError) as exc_info:
        renderer.render_html(data)

    assert "Phase 1" in str(exc_info.value)
    assert "Phase 2" in str(exc_info.value)


def test_render_markdown_with_version():
    """Test that rendered report includes version footer."""
    renderer = ReportRenderer()
    data = {
        "tenant_name": "test",
        "period": "2025",
        "audit_date": "2025-11-20",
        "overall_score": 75,
        "rules": [],
        "recommendations": [],
    }

    result = renderer.render_markdown(data)
    assert "PaidSocialNav v" in result
    assert "0.1.0" in result
