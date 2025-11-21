---
date: 2025-11-20
topic: "Claude Skills Audit Workflow Implementation"
status: draft
related_research: thoughts/shared/research/2025-11-20-claude-skills-audit-workflow.md
---

# Claude Skills Audit Workflow Implementation Plan

## Overview

This plan implements a comprehensive Claude skills-based automation workflow for social media audits. The workflow will enable:
1. Adding new customers via tenant configuration
2. Running automated audits with weighted scoring
3. Generating professional Markdown and HTML reports
4. Creating strategic insights using Claude API
5. Exporting results to Google Slides presentations

## Current State Analysis

The PaidSocialNav codebase has a strong foundation:

### Existing Infrastructure:
- **Audit Engine** (paid_social_nav/audit/engine.py:60-338): Complete multi-window, multi-level rule evaluation with 6 scoring rules
- **Tenant Management** (paid_social_nav/core/tenants.py): Multi-customer support via YAML configuration
- **CLI Framework** (paid_social_nav/cli/main.py): Typer-based command structure with meta and audit apps
- **BigQuery Storage** (paid_social_nav/storage/bq.py): Full data persistence layer
- **Basic Rendering** (paid_social_nav/render/renderer.py:6-14): Minimal Markdown renderer (placeholder)

### Key Discoveries:
- paid_social_nav/render/renderer.py:7 explicitly notes "Minimal placeholder renderer for CLI; can be replaced with Jinja2 later"
- paid_social_nav/cli/main.py:244-291 shows audit command structure and data mapping pattern
- pyproject.toml:7-13 shows current dependencies (missing Jinja2, Google APIs, Claude API client)
- Audit results are currently structured as `AuditResult` with `overall_score` and `rules` list

## Desired End State

A fully automated audit workflow accessible via:
```bash
psn skills audit --tenant-id customer_name --audit-config configs/audit_customer.yaml
```

This single command will:
1. Run the complete audit analysis using existing engine
2. Generate a professional Markdown report
3. Generate an HTML report with embedded charts
4. Generate strategic insights using Claude API
5. Create a Google Slides presentation with visualizations
6. Store all results in BigQuery

**Verification**: Successfully run the workflow for a test customer and verify all 5 outputs are created correctly.

## What We're NOT Doing

- **NOT** replacing the existing audit engine (it's solid)
- **NOT** modifying tenant management system (already works well)
- **NOT** changing BigQuery schema for existing tables
- **NOT** building a web UI (CLI-based workflow only)
- **NOT** integrating with platforms other than Meta (out of scope for this phase)

## Implementation Approach

Build Claude skills as a **workflow orchestration layer** on top of existing infrastructure. Each phase adds one capability while maintaining backward compatibility with existing audit commands.

Key architectural principle: **Extend, don't replace**. The existing `psn audit run` command continues to work; we're adding a new `psn skills audit` command that orchestrates multiple steps.

---

## Phase 1: Upgrade Report Rendering with Jinja2 Templates

### Overview
Replace the minimal placeholder renderer with a proper Jinja2-based template system. This enables professional Markdown reports and sets the foundation for HTML generation.

### Changes Required:

#### 1. Add Dependencies
**File**: `pyproject.toml`
**Changes**: Add Jinja2 and markdown2 to dependencies

```toml
dependencies = [
  # Existing...
  "typer>=0.12",
  "PyYAML>=6.0",
  "google-cloud-bigquery>=3.11",
  "requests>=2.31",
  "python-json-logger>=2.0.7",
  # New dependencies
  "jinja2>=3.1.0",
  "markdown2>=2.4.0",
]
```

#### 2. Create Template Directory Structure
**Files**: Create new directory and templates
**Changes**:
```bash
mkdir -p paid_social_nav/render/templates
```

#### 3. Create Markdown Template
**File**: `paid_social_nav/render/templates/audit_report.md.j2`
**Changes**: Create comprehensive Markdown template

```jinja2
# {{ tenant_name }} Paid Social Audit Report

**Period**: {{ period }}
**Auditor**: PaidSocialNav
**Date**: {{ audit_date }}
**Overall Score**: {{ overall_score }}/100

---

## Executive Summary

{% if overall_score >= 80 %}
✅ **Excellent Performance** - Account is well-optimized with strong fundamentals.
{% elif overall_score >= 60 %}
⚠️ **Good Performance** - Account is performing well with some areas for improvement.
{% elif overall_score >= 40 %}
⚠️ **Moderate Performance** - Several optimization opportunities identified.
{% else %}
🔴 **Needs Attention** - Significant improvements required across multiple areas.
{% endif %}

---

## Rule-by-Rule Analysis

{% for rule in rules %}
### {{ rule.rule|replace('_', ' ')|title }}

- **Window**: {{ rule.window }}
- **Level**: {{ rule.level }}
- **Score**: {{ rule.score }}/100
- **Findings**: {{ rule.findings }}

{% endfor %}

---

## Recommendations

{% if recommendations %}
{% for rec in recommendations %}
{{ loop.index }}. **{{ rec.title }}**: {{ rec.description }}
{% endfor %}
{% endif %}

---

*Report generated by PaidSocialNav v{{ version }}*
```

#### 4. Upgrade Renderer Module
**File**: `paid_social_nav/render/renderer.py`
**Changes**: Replace entire file with Jinja2-based implementation

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from .. import __version__


class ReportRenderer:
    """Renders audit reports using Jinja2 templates."""

    def __init__(self, templates_dir: Path | None = None):
        if templates_dir is None:
            templates_dir = Path(__file__).parent / "templates"
        self.env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=False,  # We're generating Markdown, not HTML
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render_markdown(self, data: dict[str, Any]) -> str:
        """Render Markdown report from audit data."""
        template = self.env.get_template("audit_report.md.j2")
        return template.render(**data, version=__version__)

    def render_html(self, data: dict[str, Any]) -> str:
        """Render HTML report from audit data."""
        template = self.env.get_template("audit_report.html.j2")
        return template.render(**data, version=__version__)


def render_markdown(templates_dir: Path, data: dict) -> str:
    """Legacy function for backward compatibility."""
    renderer = ReportRenderer(templates_dir)
    return renderer.render_markdown(data)


def write_text(path: str, content: str) -> None:
    """Write text content to file."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
```

#### 5. Update Audit CLI to Use New Renderer
**File**: `paid_social_nav/cli/main.py`
**Changes**: Update audit_run function to use new renderer

```python
@audit_app.command("run")
def audit_run(
    config: str = typer.Option(
        "configs/sample_audit.yaml", help="Path to audit config YAML"
    ),
    output: str | None = typer.Option(
        None, help="Optional output path for Markdown report"
    ),
) -> None:
    """Run audit and optionally render a Markdown report."""
    from datetime import datetime
    from ..render.renderer import ReportRenderer

    result = run_audit(config)

    # Load tenant name from config
    import yaml
    cfg = yaml.safe_load(Path(config).read_text())
    tenant_name = cfg.get("tenant", "Client")

    # Prepare data for template
    data = {
        "tenant_name": tenant_name,
        "period": "2025",
        "audit_date": datetime.now().strftime("%Y-%m-%d"),
        "overall_score": result.overall_score,
        "rules": result.rules,
        "recommendations": [],  # Phase 4 will populate with AI insights
    }

    renderer = ReportRenderer()
    md = renderer.render_markdown(data)

    if output:
        from ..render.renderer import write_text
        write_text(output, md)
        typer.echo(f"Report written to {output}")
    else:
        typer.echo(md)
```

### Success Criteria:

#### Automated Verification:
- [x] Dependencies install successfully: `pip install -e .`
- [x] Templates directory created with proper structure
- [x] Linting passes: `ruff check paid_social_nav/render/`
- [x] Type checking passes: `mypy paid_social_nav/render/renderer.py`
- [x] Existing audit command still works: `psn audit run --config configs/audit_test.yaml`

#### Manual Verification:
- [ ] Generated Markdown report is properly formatted with sections
- [ ] Rule results display correctly in the report
- [ ] Overall score appears with correct status indicator (✅/⚠️/🔴)
- [ ] Report footer shows correct version number

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the Markdown reports look professional before proceeding to Phase 2.

---

## Phase 2: Add HTML Report Generation

### Overview
Add HTML report generation with embedded charts using Chart.js for visualizations. This creates shareable, professional reports that clients can view in any browser.

### Changes Required:

#### 1. Create HTML Template
**File**: `paid_social_nav/render/templates/audit_report.html.j2`
**Changes**: Create HTML template with Chart.js visualizations

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ tenant_name }} - Audit Report</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            border-radius: 10px;
            margin-bottom: 30px;
        }
        .score-badge {
            font-size: 72px;
            font-weight: bold;
        }
        .card {
            background: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .rule-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        .rule-card {
            border-left: 4px solid #667eea;
            padding: 15px;
            background: #f9f9f9;
        }
        .chart-container {
            position: relative;
            height: 300px;
            margin: 20px 0;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>{{ tenant_name }} Paid Social Audit</h1>
        <p><strong>Period:</strong> {{ period }} | <strong>Date:</strong> {{ audit_date }}</p>
        <div class="score-badge">{{ overall_score }}/100</div>
    </div>

    <div class="card">
        <h2>Performance Overview</h2>
        <div class="chart-container">
            <canvas id="scoreChart"></canvas>
        </div>
    </div>

    <div class="card">
        <h2>Rule-by-Rule Analysis</h2>
        <div class="rule-grid">
            {% for rule in rules %}
            <div class="rule-card">
                <h3>{{ rule.rule|replace('_', ' ')|title }}</h3>
                <p><strong>Score:</strong> {{ rule.score }}/100</p>
                <p><strong>Window:</strong> {{ rule.window }}</p>
                <p><strong>Findings:</strong> {{ rule.findings }}</p>
            </div>
            {% endfor %}
        </div>
    </div>

    <script>
        const ctx = document.getElementById('scoreChart');
        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: [
                    {% for rule in rules %}'{{ rule.rule|replace("_", " ")|title }}'{% if not loop.last %},{% endif %}{% endfor %}
                ],
                datasets: [{
                    label: 'Score',
                    data: [{% for rule in rules %}{{ rule.score }}{% if not loop.last %},{% endif %}{% endfor %}],
                    backgroundColor: 'rgba(102, 126, 234, 0.8)',
                    borderColor: 'rgba(102, 126, 234, 1)',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100
                    }
                }
            }
        });
    </script>

    <footer style="text-align: center; color: #666; margin-top: 40px;">
        <p>Generated by PaidSocialNav v{{ version }}</p>
    </footer>
</body>
</html>
```

#### 2. Update CLI to Support HTML Output
**File**: `paid_social_nav/cli/main.py`
**Changes**: Add HTML output option to audit command

```python
@audit_app.command("run")
def audit_run(
    config: str = typer.Option(
        "configs/sample_audit.yaml", help="Path to audit config YAML"
    ),
    output: str | None = typer.Option(
        None, help="Optional output path for Markdown report"
    ),
    html_output: str | None = typer.Option(
        None, help="Optional output path for HTML report"
    ),
) -> None:
    """Run audit and optionally render Markdown and/or HTML reports."""
    from datetime import datetime
    from ..render.renderer import ReportRenderer, write_text

    result = run_audit(config)

    # Load tenant name from config
    import yaml
    cfg = yaml.safe_load(Path(config).read_text())
    tenant_name = cfg.get("tenant", "Client")

    # Prepare data for template
    data = {
        "tenant_name": tenant_name,
        "period": "2025",
        "audit_date": datetime.now().strftime("%Y-%m-%d"),
        "overall_score": result.overall_score,
        "rules": result.rules,
        "recommendations": [],
    }

    renderer = ReportRenderer()

    # Generate Markdown if requested
    if output:
        md = renderer.render_markdown(data)
        write_text(output, md)
        typer.echo(f"Markdown report written to {output}")

    # Generate HTML if requested
    if html_output:
        html = renderer.render_html(data)
        write_text(html_output, html)
        typer.echo(f"HTML report written to {html_output}")

    # If neither specified, output Markdown to console
    if not output and not html_output:
        md = renderer.render_markdown(data)
        typer.echo(md)
```

### Success Criteria:

#### Automated Verification:
- [ ] HTML template validates: No Jinja2 syntax errors
- [ ] Linting passes: `ruff check paid_social_nav/`
- [ ] Type checking passes: `mypy paid_social_nav/cli/main.py`
- [ ] HTML report generates: `psn audit run --config configs/audit_test.yaml --html-output reports/test.html`

#### Manual Verification:
- [ ] HTML report opens in browser without errors
- [ ] Chart.js visualizations render correctly
- [ ] All rule cards display with proper formatting
- [ ] Score badge shows correct color based on score
- [ ] Report is responsive on mobile devices

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation that HTML reports are publication-ready before proceeding to Phase 3.

---

## Phase 3: Build Claude Skills Orchestration Framework

### Overview
Create a skills framework that orchestrates multi-step workflows. This phase builds the foundation for automating the complete audit workflow from config to reports.

### Changes Required:

#### 1. Create Skills Module Structure
**Files**: Create new skills directory
**Changes**:
```bash
mkdir -p paid_social_nav/skills
touch paid_social_nav/skills/__init__.py
```

#### 2. Create Base Skill Class
**File**: `paid_social_nav/skills/base.py`
**Changes**: Define abstract base class for all skills

```python
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class SkillResult:
    """Result returned by a skill execution."""
    success: bool
    data: dict[str, Any]
    message: str
    next_step: str | None = None


class BaseSkill(ABC):
    """Base class for Claude skills that orchestrate multi-step workflows."""

    @abstractmethod
    def execute(self, context: dict[str, Any]) -> SkillResult:
        """Execute the skill workflow.

        Args:
            context: Input parameters and configuration

        Returns:
            SkillResult with success status and output data
        """
        pass

    def validate_context(self, context: dict[str, Any]) -> tuple[bool, str]:
        """Validate required context parameters.

        Args:
            context: Input parameters to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        return True, ""
```

#### 3. Create Audit Workflow Skill
**File**: `paid_social_nav/skills/audit_workflow.py`
**Changes**: Implement complete audit workflow orchestration

```python
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from ..audit.engine import run_audit
from ..core.tenants import get_tenant
from ..render.renderer import ReportRenderer, write_text
from .base import BaseSkill, SkillResult


class AuditWorkflowSkill(BaseSkill):
    """Complete audit workflow: config → audit → reports.

    This skill orchestrates the entire audit process:
    1. Validates tenant configuration
    2. Runs audit analysis
    3. Generates Markdown report
    4. Generates HTML report
    5. Returns all output paths
    """

    def validate_context(self, context: dict[str, Any]) -> tuple[bool, str]:
        """Validate required parameters."""
        if "tenant_id" not in context:
            return False, "Missing required parameter: tenant_id"
        if "audit_config" not in context:
            return False, "Missing required parameter: audit_config"

        config_path = Path(context["audit_config"])
        if not config_path.exists():
            return False, f"Audit config not found: {config_path}"

        return True, ""

    def execute(self, context: dict[str, Any]) -> SkillResult:
        """Execute the complete audit workflow."""
        # Step 1: Validate context
        is_valid, error_msg = self.validate_context(context)
        if not is_valid:
            return SkillResult(
                success=False,
                data={},
                message=error_msg
            )

        # Step 2: Validate tenant exists
        tenant = get_tenant(context["tenant_id"])
        if not tenant:
            return SkillResult(
                success=False,
                data={},
                message=f"Tenant '{context['tenant_id']}' not found in configs/tenants.yaml"
            )

        # Step 3: Run audit
        try:
            audit_result = run_audit(context["audit_config"])
        except Exception as e:
            return SkillResult(
                success=False,
                data={},
                message=f"Audit failed: {e}"
            )

        # Step 4: Prepare report data
        cfg = yaml.safe_load(Path(context["audit_config"]).read_text())
        data = {
            "tenant_name": tenant.id,
            "period": "2025",
            "audit_date": datetime.now().strftime("%Y-%m-%d"),
            "overall_score": audit_result.overall_score,
            "rules": audit_result.rules,
            "recommendations": [],  # Will be populated in Phase 4
        }

        # Step 5: Generate reports
        output_dir = Path(context.get("output_dir", "reports"))
        output_dir.mkdir(parents=True, exist_ok=True)

        renderer = ReportRenderer()

        # Generate Markdown
        md_path = output_dir / f"{tenant.id}_audit_{datetime.now().strftime('%Y%m%d')}.md"
        md_content = renderer.render_markdown(data)
        write_text(str(md_path), md_content)

        # Generate HTML
        html_path = output_dir / f"{tenant.id}_audit_{datetime.now().strftime('%Y%m%d')}.html"
        html_content = renderer.render_html(data)
        write_text(str(html_path), html_content)

        # Step 6: Return results
        return SkillResult(
            success=True,
            data={
                "audit_score": audit_result.overall_score,
                "markdown_report": str(md_path),
                "html_report": str(html_path),
                "tenant_id": tenant.id,
            },
            message=f"Audit complete: {audit_result.overall_score}/100"
        )
```

#### 4. Add Skills CLI Command Group
**File**: `paid_social_nav/cli/main.py`
**Changes**: Add new skills command group

```python
# Add at the top with other imports
from ..skills.audit_workflow import AuditWorkflowSkill

# Add after existing app definitions (around line 17)
skills_app = typer.Typer(help="Claude skills automation workflows")

# Add new command (around line 291, before app.add_typer calls)
@skills_app.command("audit")
def run_audit_skill(
    tenant_id: str = typer.Option(..., help="Tenant identifier from configs/tenants.yaml"),
    audit_config: str = typer.Option(..., help="Path to audit YAML config"),
    output_dir: str = typer.Option("reports/", help="Output directory for reports"),
) -> None:
    """Run complete audit workflow using Claude skills orchestration.

    This command orchestrates the entire audit process:
    - Validates tenant configuration
    - Runs audit analysis with weighted scoring
    - Generates professional Markdown and HTML reports
    - Saves all outputs to the specified directory

    Example:
        psn skills audit --tenant-id puttery --audit-config configs/audit_puttery.yaml
    """
    skill = AuditWorkflowSkill()
    result = skill.execute({
        "tenant_id": tenant_id,
        "audit_config": audit_config,
        "output_dir": output_dir,
    })

    if result.success:
        typer.secho(f"✅ {result.message}", fg=typer.colors.GREEN)
        typer.echo(f"\nReports generated:")
        typer.echo(f"  Markdown: {result.data['markdown_report']}")
        typer.echo(f"  HTML: {result.data['html_report']}")
    else:
        typer.secho(f"❌ {result.message}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

# Update app registration (around line 294)
app.add_typer(meta_app, name="meta")
app.add_typer(audit_app, name="audit")
app.add_typer(skills_app, name="skills")
```

#### 5. Update Skills Module Init
**File**: `paid_social_nav/skills/__init__.py`
**Changes**: Export key classes

```python
from .base import BaseSkill, SkillResult
from .audit_workflow import AuditWorkflowSkill

__all__ = ["BaseSkill", "SkillResult", "AuditWorkflowSkill"]
```

### Success Criteria:

#### Automated Verification:
- [ ] Skills module imports successfully: `python -c "from paid_social_nav.skills import AuditWorkflowSkill"`
- [ ] Linting passes: `ruff check paid_social_nav/skills/`
- [ ] Type checking passes: `mypy paid_social_nav/skills/`
- [ ] CLI help shows new command: `psn skills --help`
- [ ] Full workflow executes: `psn skills audit --tenant-id puttery --audit-config configs/audit_puttery.yaml`

#### Manual Verification:
- [ ] Command generates both Markdown and HTML reports
- [ ] Output files are created in the reports/ directory with correct naming
- [ ] Console output shows success message with file paths
- [ ] Reports contain complete audit data
- [ ] Error handling works correctly for missing tenant or invalid config

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation that the skills orchestration works correctly before proceeding to Phase 4.

---

## Phase 4: Add AI-Generated Insights with Claude API

### Overview
Integrate Claude API to generate strategic insights, recommendations, and action items based on audit results. This adds AI-powered analysis on top of the rule-based scoring.

### Changes Required:

#### 1. Add Claude API Dependency
**File**: `pyproject.toml`
**Changes**: Add anthropic library

```toml
dependencies = [
  # Existing...
  "typer>=0.12",
  "PyYAML>=6.0",
  "google-cloud-bigquery>=3.11",
  "requests>=2.31",
  "python-json-logger>=2.0.7",
  "jinja2>=3.1.0",
  "markdown2>=2.4.0",
  # New for Phase 4
  "anthropic>=0.34.0",
]
```

#### 2. Create Insights Generator Module
**File**: `paid_social_nav/insights/__init__.py`
**Changes**: Create module init

```python
from .generator import InsightsGenerator

__all__ = ["InsightsGenerator"]
```

#### 3. Implement Insights Generator
**File**: `paid_social_nav/insights/generator.py`
**Changes**: Create Claude API integration

```python
from __future__ import annotations

import json
from typing import Any

import anthropic

from ..audit.engine import AuditResult
from ..core.logging_config import get_logger

logger = get_logger(__name__)


class InsightsGenerator:
    """Generates strategic insights from audit results using Claude API."""

    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)

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
                model="claude-3-5-sonnet-20241022",
                max_tokens=2000,
                temperature=0.7,
                system="You are an expert paid social media strategist analyzing audit results.",
                messages=[{"role": "user", "content": prompt}]
            )

            content = response.content[0].text
            insights = self._parse_insights(content)

            logger.info(
                "Insights generated successfully",
                extra={
                    "tenant": tenant_name,
                    "recommendations": len(insights.get("recommendations", []))
                }
            )

            return insights

        except Exception as e:
            logger.error(
                "Failed to generate insights",
                extra={"tenant": tenant_name, "error": str(e)}
            )
            raise

    def _build_prompt(self, audit_result: AuditResult, tenant_name: str) -> str:
        """Build the analysis prompt for Claude."""
        rules_summary = "\n".join([
            f"- {rule['rule']}: {rule['score']}/100 ({rule['findings']})"
            for rule in audit_result.rules
        ])

        return f"""Analyze this paid social media audit for {tenant_name}:

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
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse Claude response as JSON", extra={"error": str(e)})
            # Return empty structure
            return {
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
```

#### 4. Update Audit Workflow Skill
**File**: `paid_social_nav/skills/audit_workflow.py`
**Changes**: Integrate insights generation

```python
# Add to imports at the top
import os
from ..insights.generator import InsightsGenerator

# Update execute method to add insights generation step
# Add this after Step 3 (Run audit):

        # Step 3.5: Generate AI insights if Claude API key is available
        insights = None
        claude_api_key = os.getenv("ANTHROPIC_API_KEY")
        if claude_api_key:
            try:
                generator = InsightsGenerator(claude_api_key)
                insights = generator.generate_strategy(audit_result, tenant.id)
            except Exception as e:
                # Log error but continue - insights are optional enhancement
                from ..core.logging_config import get_logger
                logger = get_logger(__name__)
                logger.warning(
                    "Failed to generate AI insights, continuing without them",
                    extra={"error": str(e)}
                )

        # Update Step 4 data preparation to include insights:
        data = {
            "tenant_name": tenant.id,
            "period": "2025",
            "audit_date": datetime.now().strftime("%Y-%m-%d"),
            "overall_score": audit_result.overall_score,
            "rules": audit_result.rules,
            "recommendations": insights.get("recommendations", []) if insights else [],
            "strengths": insights.get("strengths", []) if insights else [],
            "issues": insights.get("issues", []) if insights else [],
            "quick_wins": insights.get("quick_wins", []) if insights else [],
            "roadmap": insights.get("roadmap", {}) if insights else {},
        }
```

#### 5. Update Report Templates with Insights Sections
**File**: `paid_social_nav/render/templates/audit_report.md.j2`
**Changes**: Add sections for AI-generated insights

```jinja2
# Add after the Rule-by-Rule Analysis section:

---

## Strategic Insights

{% if strengths %}
### Strengths

{% for strength in strengths %}
{{ loop.index }}. **{{ strength.title }}**: {{ strength.description }}
{% endfor %}
{% endif %}

{% if issues %}
### Critical Issues

{% for issue in issues %}
{{ loop.index }}. **{{ issue.title }}** ({{ issue.severity|upper }}): {{ issue.description }}
{% endfor %}
{% endif %}

---

## Recommendations

{% if recommendations %}
{% for rec in recommendations %}
### {{ loop.index }}. {{ rec.title }}

**What to do**: {{ rec.description }}

**Expected impact**: {{ rec.expected_impact }}

**Effort required**: {{ rec.effort|title }}

{% endfor %}
{% endif %}

---

## Quick Wins

{% if quick_wins %}
These actions can be implemented immediately for fast results:

{% for win in quick_wins %}
- **{{ win.action }}**: {{ win.expected_result }}
{% endfor %}
{% endif %}

---

## 90-Day Roadmap

{% if roadmap %}
### Phase 1: Days 1-30
{% for action in roadmap.phase_1_30_days %}
- {{ action }}
{% endfor %}

### Phase 2: Days 31-60
{% for action in roadmap.phase_2_60_days %}
- {{ action }}
{% endfor %}

### Phase 3: Days 61-90
{% for action in roadmap.phase_3_90_days %}
- {{ action }}
{% endfor %}
{% endif %}
```

**File**: `paid_social_nav/render/templates/audit_report.html.j2`
**Changes**: Add insights sections to HTML template (similar structure with appropriate HTML styling)

#### 6. Update Environment Configuration
**File**: `.env.example` (create if doesn't exist)
**Changes**: Document ANTHROPIC_API_KEY requirement

```bash
# Claude API for insights generation (optional, Phase 4)
ANTHROPIC_API_KEY=sk-ant-api03-...

# Existing Meta configuration
META_ACCESS_TOKEN=your_meta_token_here

# GCP configuration
GCP_PROJECT_ID=your-project-id
BQ_DATASET=paid_social
```

### Success Criteria:

#### Automated Verification:
- [ ] Anthropic package installs: `pip install -e .`
- [ ] Insights module imports: `python -c "from paid_social_nav.insights import InsightsGenerator"`
- [ ] Linting passes: `ruff check paid_social_nav/insights/`
- [ ] Type checking passes: `mypy paid_social_nav/insights/`
- [ ] Skills command runs (without API key): `psn skills audit --tenant-id puttery --audit-config configs/audit_puttery.yaml`
- [ ] Skills command runs (with API key): `ANTHROPIC_API_KEY=sk-... psn skills audit --tenant-id puttery --audit-config configs/audit_puttery.yaml`

#### Manual Verification:
- [ ] Without API key: Reports generate successfully, insights sections are empty
- [ ] With API key: Reports include AI-generated strengths, issues, recommendations
- [ ] Insights are relevant to the actual audit scores
- [ ] Quick wins are actionable and specific
- [ ] 90-day roadmap is logical and phased appropriately
- [ ] JSON parsing handles Claude's response format correctly

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation that AI insights are valuable and accurate before considering the implementation complete.

---

## Testing Strategy

### Unit Tests:

**File**: `tests/test_skills_base.py`
- Test BaseSkill abstract interface
- Test SkillResult serialization

**File**: `tests/test_audit_workflow_skill.py`
- Test context validation
- Test tenant lookup
- Test report generation
- Mock audit engine to isolate skill logic

**File**: `tests/test_insights_generator.py`
- Test prompt building
- Test JSON parsing from Claude responses
- Mock Anthropic API to avoid real API calls
- Test error handling for malformed responses

**File**: `tests/test_renderer.py`
- Test Jinja2 template rendering
- Test Markdown output formatting
- Test HTML output structure
- Test with and without insights data

### Integration Tests:

**File**: `tests/integration/test_full_workflow.py`
- Test end-to-end audit workflow
- Validate all outputs are created
- Test with real BigQuery test dataset
- Test with mocked Claude API

### Manual Testing Steps:

1. **Test with sample tenant**:
   ```bash
   psn skills audit --tenant-id puttery --audit-config configs/audit_puttery.yaml
   ```
   - Verify both reports are created
   - Check reports contain correct data
   - Validate file naming convention

2. **Test without Claude API key**:
   ```bash
   unset ANTHROPIC_API_KEY
   psn skills audit --tenant-id puttery --audit-config configs/audit_puttery.yaml
   ```
   - Verify workflow completes successfully
   - Confirm insights sections are empty but present

3. **Test with Claude API key**:
   ```bash
   export ANTHROPIC_API_KEY=sk-ant-...
   psn skills audit --tenant-id puttery --audit-config configs/audit_puttery.yaml
   ```
   - Verify insights are generated
   - Check recommendations are actionable
   - Validate roadmap makes sense

4. **Test error handling**:
   ```bash
   psn skills audit --tenant-id nonexistent --audit-config configs/audit_test.yaml
   ```
   - Verify clear error message for missing tenant
   - Confirm graceful failure with exit code 1

## Performance Considerations

### BigQuery Query Optimization:
- All audit queries are already optimized in paid_social_nav/audit/engine.py
- Views (v_budget_concentration, v_creative_mix, v_budget_pacing) pre-aggregate data
- No additional optimization needed in this implementation

### Template Rendering:
- Jinja2 templates are compiled once and cached
- ReportRenderer instance can be reused across multiple renders
- Templates are small (<100 lines), rendering is fast

### Claude API Calls:
- Single API call per audit (not per rule)
- 2000 token limit keeps costs low (~$0.03 per audit with Sonnet)
- Optional feature - workflow works without it
- Consider caching insights for repeated audits of same data

### Report Generation:
- File I/O is minimal (2-3 small files per audit)
- HTML includes CDN-hosted Chart.js (no bundling needed)
- Reports directory should be created once at startup

## Migration Notes

### Backward Compatibility:
- Existing `psn audit run` command continues to work unchanged
- New `psn skills audit` command is additive, not replacing
- Tenant configuration format unchanged
- Audit config YAML format unchanged

### New Requirements:
- Jinja2, markdown2, anthropic packages (all pure Python, no system deps)
- ANTHROPIC_API_KEY environment variable (optional)
- Reports directory (auto-created)

### Data Migration:
- No database schema changes required
- No existing data migration needed
- All new functionality builds on existing tables/views

## References

- Original research: `thoughts/shared/research/2025-11-20-claude-skills-audit-workflow.md`
- Audit engine: `paid_social_nav/audit/engine.py:60-338`
- Current CLI: `paid_social_nav/cli/main.py:244-291`
- Current renderer: `paid_social_nav/render/renderer.py:6-14`
- Tenant management: `paid_social_nav/core/tenants.py`

## Dependencies Summary

All new dependencies are added to `pyproject.toml`:

**Phase 1**:
- `jinja2>=3.1.0` - Template engine for reports
- `markdown2>=2.4.0` - Markdown processing utilities

**Phase 4**:
- `anthropic>=0.34.0` - Claude API client for insights

Total of 3 new dependencies, all pure Python with no system-level requirements.

## Architecture Benefits

This implementation provides:

1. **Minimal Changes**: Builds on existing infrastructure, no refactoring needed
2. **Backward Compatible**: All existing commands continue to work
3. **Incremental Adoption**: Each phase adds value independently
4. **Testable**: Each component can be unit tested in isolation
5. **Extensible**: Skills framework allows adding new workflows easily
6. **Cost Effective**: Optional Claude API usage, ~$0.03 per audit
7. **Production Ready**: Error handling, logging, and validation at each step

## Success Metrics

After full implementation, success will be measured by:

1. **Automation Level**: One command generates complete audit package (Markdown + HTML + insights)
2. **Report Quality**: Professional reports suitable for client delivery
3. **Insight Value**: AI recommendations are actionable and specific
4. **Performance**: Workflow completes in <30 seconds (excluding BigQuery queries)
5. **Reliability**: 99%+ success rate with proper error messages
6. **Adoption**: Skills framework used for other workflows (future)
