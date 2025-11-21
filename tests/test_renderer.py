"""Tests for the report renderer."""
from __future__ import annotations

from pathlib import Path
import tempfile

from paid_social_nav.render.renderer import ReportRenderer, write_text


def test_renderer_instantiation() -> None:
    """Test that ReportRenderer can be instantiated."""
    renderer = ReportRenderer()
    assert renderer is not None
    assert renderer.env is not None


def test_render_markdown_basic() -> None:
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


def test_render_markdown_with_rules() -> None:
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


def test_render_markdown_score_ranges() -> None:
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


def test_render_html_basic() -> None:
    """Test basic HTML rendering with minimal data."""
    renderer = ReportRenderer()
    data = {
        "tenant_name": "test_client",
        "period": "Q4 2025",
        "audit_date": "2025-11-20",
        "overall_score": 75,
        "rules": [],
        "recommendations": [],
    }

    result = renderer.render_html(data)

    # Check HTML structure
    assert "<!DOCTYPE html>" in result
    assert "<html" in result
    assert "test_client" in result
    assert "75/100" in result
    assert "Q4 2025" in result
    assert "2025-11-20" in result
    # Check Chart.js is included
    assert "chart.js" in result.lower()
    assert "<canvas id=\"scoreChart\">" in result


def test_render_html_with_rules() -> None:
    """Test HTML rendering with rule data."""
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
            },
            {
                "rule": "creative_diversity",
                "window": "30d",
                "level": "ad",
                "score": 70,
                "findings": "Some creative fatigue detected"
            }
        ],
        "recommendations": [],
    }

    result = renderer.render_html(data)

    # Check that rule cards are present
    assert "Budget Concentration" in result
    assert "Creative Diversity" in result
    assert "85" in result  # Score for budget_concentration
    assert "70" in result  # Score for creative_diversity
    # Check Chart.js data array includes both scores
    assert "datasets" in result


def test_render_markdown_with_version() -> None:
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


def test_render_html_with_version() -> None:
    """Test that HTML report includes version footer."""
    renderer = ReportRenderer()
    data = {
        "tenant_name": "test",
        "period": "2025",
        "audit_date": "2025-11-20",
        "overall_score": 75,
        "rules": [],
        "recommendations": [],
    }

    result = renderer.render_html(data)
    assert "PaidSocialNav v" in result
    assert "0.1.0" in result


def test_write_text() -> None:
    """Test that write_text creates parent directories and writes content."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Test writing to a nested path that doesn't exist
        test_path = Path(tmpdir) / "subdir" / "nested" / "test.txt"
        test_content = "Test content"

        write_text(str(test_path), test_content)

        # Verify file was created
        assert test_path.exists()
        assert test_path.is_file()

        # Verify content
        assert test_path.read_text(encoding="utf-8") == test_content


def test_write_text_overwrites_existing() -> None:
    """Test that write_text overwrites existing files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_path = Path(tmpdir) / "test.txt"

        # Write initial content
        write_text(str(test_path), "Initial content")
        assert test_path.read_text(encoding="utf-8") == "Initial content"

        # Overwrite with new content
        write_text(str(test_path), "New content")
        assert test_path.read_text(encoding="utf-8") == "New content"


def test_html_xss_protection() -> None:
    """Test that HTML template properly escapes potentially malicious content."""
    renderer = ReportRenderer()

    # Data with XSS attack vectors
    data = {
        "tenant_name": "<script>alert('XSS')</script>",
        "period": "<img src=x onerror=alert('XSS')>",
        "audit_date": "2025-11-20",
        "overall_score": 75,
        "rules": [
            {
                "rule": "test_rule<script>alert('XSS')</script>",
                "window": "30d",
                "level": "campaign",
                "score": 85,
                "findings": "<script>alert('XSS')</script>"
            }
        ],
        "recommendations": [],
    }

    result = renderer.render_html(data)

    # Verify that dangerous characters are escaped
    assert "<script>alert('XSS')</script>" not in result
    assert "&lt;script&gt;" in result or "\\u003c" in result  # JSON or HTML escaped
    assert "&lt;img" in result or "\\u003c" in result

    # Verify the document still has valid structure
    assert "<!DOCTYPE html>" in result
    assert "<html" in result


def test_html_sri_integrity() -> None:
    """Test that external scripts use SRI for security."""
    renderer = ReportRenderer()
    data = {
        "tenant_name": "test",
        "period": "2025",
        "audit_date": "2025-11-20",
        "overall_score": 75,
        "rules": [],
        "recommendations": [],
    }

    result = renderer.render_html(data)

    # Verify Chart.js has integrity and crossorigin attributes
    assert "integrity=" in result
    assert "crossorigin=" in result
    assert "sha384-" in result


def test_markdown_no_escape() -> None:
    """Test that Markdown template does not escape HTML entities."""
    renderer = ReportRenderer()

    # Markdown can contain HTML-like syntax that shouldn't be escaped
    data = {
        "tenant_name": "Test <Company>",
        "period": "2025",
        "audit_date": "2025-11-20",
        "overall_score": 75,
        "rules": [],
        "recommendations": [],
    }

    result = renderer.render_markdown(data)

    # In Markdown, we want the raw content (no HTML escaping)
    assert "Test <Company>" in result
    assert "&lt;" not in result  # Should NOT be HTML-escaped
