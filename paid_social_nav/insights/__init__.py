"""Strategic insights package for AI-powered audit analysis.

This package provides intelligent analysis capabilities that transform raw audit metrics
into strategic, actionable insights using Claude AI. It acts as the intelligence layer
that bridges technical audit data and business strategy for paid social advertisers.

The insights system leverages Claude's reasoning capabilities to:
    - Identify key strengths in current advertising strategy
    - Highlight critical issues requiring immediate attention
    - Generate specific, ranked recommendations for improvement
    - Suggest quick wins for rapid impact
    - Provide a 90-day implementation roadmap

Main Components:
    - InsightsGenerator: Claude-powered analysis engine for audit results

Usage:
    from paid_social_nav.insights import InsightsGenerator

    generator = InsightsGenerator(api_key="sk-...")
    insights = generator.generate_strategy(
        audit_result=audit_result,
        tenant_name="client_name"
    )

    for strength in insights.get("strengths", []):
        print(f"Strength: {strength['title']}")

Architecture Notes:
    - Built on Claude AI for intelligent analysis
    - Sanitizes inputs to prevent prompt injection attacks
    - Returns consistent JSON structures even on API errors
    - Supports enterprise audit contexts with proper logging

Integration Notes:
    - Works with AuditResult objects from the audit module
    - Structured output suitable for HTML report templates
    - Designed for batch and real-time analysis scenarios
"""

from .generator import InsightsGenerator

__all__ = ["InsightsGenerator"]
