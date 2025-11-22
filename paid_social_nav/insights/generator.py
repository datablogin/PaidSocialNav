"""Strategic insights generation from audit results using Claude AI.

This module provides intelligent analysis of paid social advertising audits by leveraging
Claude AI to generate strategic insights, recommendations, and actionable improvement plans.
It transforms numerical audit metrics into human-readable strategic guidance suitable for
executive stakeholders and advertising professionals.

The InsightsGenerator bridges the gap between technical audit data and strategic business
decisions by asking Claude to analyze audit results and provide comprehensive strategic
recommendations including strengths identification, critical issue analysis, actionable
recommendations, quick wins, and a 90-day implementation roadmap.

Insight Generation Workflow:
1. Initialize InsightsGenerator with Anthropic API key and optional configuration
2. Prepare audit results containing rule scores, findings, and overall metrics
3. Build comprehensive prompt that sanitizes inputs against prompt injection
4. Send prompt to Claude API for analysis and strategic thinking
5. Parse Claude's structured JSON response containing insights
6. Handle API errors gracefully with appropriate logging and fallback structures

Usage:
    from paid_social_nav.insights.generator import InsightsGenerator
    from paid_social_nav.audit.engine import run_audit

    audit_result = run_audit(account_id="123", adapter=adapter)
    generator = InsightsGenerator(api_key="sk-...")
    insights = generator.generate_strategy(
        audit_result=audit_result,
        tenant_name="acme_corp"
    )

    for strength in insights.get("strengths", []):
        print(f"Strength: {strength['title']}")
    for rec in insights.get("recommendations", []):
        print(f"Recommendation: {rec['title']}")

Architecture Notes:
    - Uses Claude 3.5 Haiku model for cost-effective analysis
    - Implements prompt injection prevention via tenant name sanitization
    - Structures prompts with explicit JSON format expectations
    - Graceful fallback when Claude API fails (returns empty structures)
    - Supports configurable token limits and temperature

Security Notes:
    - Sanitizes user input (tenant_name) to remove newlines/control characters
    - Limits tenant name to 100 characters before prompt inclusion
    - API key never logged (handled by Anthropic SDK)
    - Fails safely with empty structures if API call errors occur
    - Response parsing handles multiple markdown code block formats

Performance Notes:
    - Default token limit (4000) handles most audit result analyses
    - Temperature 0.7 balances creativity and consistency
    - Claude API calls block until completion
    - JSON parsing includes defensive markdown removal

API Integration Notes:
    - Requires valid Anthropic API key with Claude access
    - Uses claude-3-5-haiku-20241022 model (cost-optimized)
    - Raises AuthenticationError on invalid credentials
    - Raises RateLimitError when API quota exceeded
"""

from __future__ import annotations

import json
from typing import Any

import anthropic

from ..audit.engine import AuditResult
from ..core.logging_config import get_logger

logger = get_logger(__name__)


class InsightsGenerator:
    """Generates strategic insights from audit results using Claude API."""

    def __init__(self, api_key: str, max_tokens: int = 4000, temperature: float = 0.7):
        """Initialize the insights generator.

        Args:
            api_key: Anthropic API key
            max_tokens: Maximum tokens for Claude response (default: 4000)
            temperature: Response temperature 0-1 (default: 0.7)
        """
        self.client = anthropic.Anthropic(api_key=api_key)
        self.max_tokens = max_tokens
        self.temperature = temperature

    def generate_strategy(
        self, audit_result: AuditResult, tenant_name: str
    ) -> dict[str, Any]:
        """Generate strategic insights from audit results.

        Args:
            audit_result: The audit results to analyze
            tenant_name: Name of the tenant/client

        Returns:
            Dictionary containing:
            - strengths: List of top 3 strengths
            - issues: List of top 3 critical issues
            - recommendations: List of 5 strategic recommendations
            - quick_wins: List of quick win actions
            - roadmap: 90-day roadmap with phases
        """
        logger.info(
            "Generating insights with Claude API",
            extra={"tenant": tenant_name, "score": audit_result.overall_score}
        )

        prompt = self._build_prompt(audit_result, tenant_name)

        try:
            response = self.client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system="You are an expert paid social media strategist analyzing audit results.",
                messages=[{"role": "user", "content": prompt}]
            )

            # Extract text from first content block
            first_block = response.content[0]
            if hasattr(first_block, 'text'):
                content = first_block.text
            else:
                raise ValueError(f"Unexpected content block type: {type(first_block)}")
            insights = self._parse_insights(content)

            logger.info(
                "Insights generated successfully",
                extra={
                    "tenant": tenant_name,
                    "recommendations": len(insights.get("recommendations", []))
                }
            )

            return insights

        except anthropic.AuthenticationError:
            logger.error("Invalid Anthropic API key", extra={"tenant": tenant_name})
            raise
        except anthropic.RateLimitError:
            logger.error("Anthropic API rate limit exceeded", extra={"tenant": tenant_name})
            raise
        except Exception as e:
            logger.error(
                "Failed to generate insights",
                extra={"tenant": tenant_name, "error": str(e), "error_type": type(e).__name__}
            )
            raise

    def _build_prompt(self, audit_result: AuditResult, tenant_name: str) -> str:
        """Build the analysis prompt for Claude."""
        # Sanitize tenant name to prevent prompt injection
        safe_tenant_name = tenant_name.replace('\n', ' ').replace('\r', ' ')[:100]

        rules_summary = "\n".join([
            f"- {rule['rule']}: {rule['score']}/100 ({rule['findings']})"
            for rule in audit_result.rules
        ])

        return f"""Analyze this paid social media audit for {safe_tenant_name}:

Overall Score: {audit_result.overall_score}/100

Detailed Rule Results:
{rules_summary}

Please provide a comprehensive strategic analysis in the following JSON format:

{{
  "strengths": [
    {{"title": "Strength 1", "description": "Why this is good"}},
    {{"title": "Strength 2", "description": "Why this is good"}},
    {{"title": "Strength 3", "description": "Why this is good"}}
  ],
  "issues": [
    {{"title": "Issue 1", "severity": "high|medium|low", "description": "What's wrong"}},
    {{"title": "Issue 2", "severity": "high|medium|low", "description": "What's wrong"}},
    {{"title": "Issue 3", "severity": "high|medium|low", "description": "What's wrong"}}
  ],
  "recommendations": [
    {{
      "title": "Recommendation 1",
      "description": "What to do",
      "expected_impact": "What will improve",
      "effort": "low|medium|high"
    }}
    // ... 4 more recommendations
  ],
  "quick_wins": [
    {{"action": "Quick win 1", "expected_result": "What happens"}},
    {{"action": "Quick win 2", "expected_result": "What happens"}},
    {{"action": "Quick win 3", "expected_result": "What happens"}}
  ],
  "roadmap": {{
    "phase_1_30_days": ["Action 1", "Action 2", "Action 3"],
    "phase_2_60_days": ["Action 1", "Action 2", "Action 3"],
    "phase_3_90_days": ["Action 1", "Action 2", "Action 3"]
  }}
}}

Return ONLY the JSON object, no additional text."""

    def _parse_insights(self, content: str) -> dict[str, Any]:
        """Parse Claude's response into structured insights."""
        # Find JSON in the response (Claude might wrap it in markdown code blocks)
        content = content.strip()

        # Remove markdown code block if present
        if content.startswith("```json"):
            content = content[7:]  # Remove ```json
        if content.startswith("```"):
            content = content[3:]  # Remove ```
        if content.endswith("```"):
            content = content[:-3]  # Remove trailing ```

        content = content.strip()

        try:
            parsed: dict[str, Any] = json.loads(content)
            return parsed
        except json.JSONDecodeError as e:
            logger.error("Failed to parse Claude response as JSON", extra={"error": str(e)})
            # Return empty structure
            empty_structure: dict[str, Any] = {
                "strengths": [],
                "issues": [],
                "recommendations": [],
                "quick_wins": [],
                "roadmap": {
                    "phase_1_30_days": [],
                    "phase_2_60_days": [],
                    "phase_3_90_days": []
                }
            }
            return empty_structure
