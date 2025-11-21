---
date: 2025-11-20T00:00:00-08:00
researcher: Claude Code
git_commit: 170e992aefee225947a7ee6c024709033c451c11
branch: feature/issue-20-fallback-multilevel-chunking
repository: PaidSocialNav
topic: "Implementing Claude Skills for Social Media Audit Workflow"
tags: [research, codebase, claude-skills, audit, workflow, reports]
status: complete
last_updated: 2025-11-20
last_updated_by: Claude Code
---

# Research: Implementing Claude Skills for Social Media Audit Workflow

**Date**: 2025-11-20T00:00:00-08:00
**Researcher**: Claude Code
**Git Commit**: 170e992aefee225947a7ee6c024709033c451c11
**Branch**: feature/issue-20-fallback-multilevel-chunking
**Repository**: PaidSocialNav

## Research Question

What's the best way to implement Claude skills for automating social media audits? The workflow should:
1. Add new customers
2. Store audit results
3. Apply audit best practices
4. Generate Markdown and HTML reports
5. Create insights, strategy, and graphs in Google Slides

## Summary

The PaidSocialNav codebase has a **strong foundation** for implementing Claude skills-based audit automation. Key existing components include:

- **Robust audit engine** with 6 rule categories and weighted scoring (paid_social_nav/audit/engine.py)
- **Tenant management system** for multi-customer support (configs/tenants.yaml, paid_social_nav/core/tenants.py)
- **CLI framework** built on Typer with extensible command structure (paid_social_nav/cli/main.py)
- **Report rendering** infrastructure with Markdown support (paid_social_nav/render/renderer.py)
- **BigQuery-backed storage** for audit results and analytics (paid_social_nav/storage/bq.py)

**Gaps to fill**: HTML report generation, Google Slides integration, and Claude skills orchestration layer.

**Recommended approach**: Build Claude skills as a workflow orchestration layer on top of existing infrastructure, following the established CLI command pattern.

## Detailed Findings

### Existing Audit Infrastructure

The codebase already implements most audit workflow components:

**Audit Engine** (paid_social_nav/audit/engine.py:1-331):
- `AuditEngine` class orchestrates multi-window, multi-level rule evaluation
- 6 scoring rules: budget pacing, CTR, frequency, budget concentration, creative diversity, tracking health
- Weighted scoring system with configurable thresholds
- BigQuery integration for KPI fetching

**Audit Rules** (paid_social_nav/audit/rules.py:1-200+):
- `pacing_vs_target()` - Budget pacing analysis
- `ctr_threshold()` - Click-through rate evaluation
- `frequency_threshold()` - Ad frequency management
- `budget_concentration()` - Top-N spend concentration
- `creative_diversity()` - Video/image content mix
- `tracking_health()` - Conversion tracking validation

**CLI Integration** (paid_social_nav/cli/main.py:244-290):
```bash
psn audit run --config configs/audit_puttery.yaml --output reports/output.md
```

### Tenant/Customer Management

**Configuration System** (configs/tenants.yaml):
```yaml
tenants:
  puttery:
    project_id: puttery-golf-001
    dataset: paid_social
    default_level: campaign
    meta_account_id: act_229793224304371
```

**Adding new customers** is already streamlined:
1. Add tenant entry to configs/tenants.yaml
2. Create optional audit config (configs/audit_<customer>.yaml)
3. Store Meta API token in GCP Secret Manager or .env file

**Tenant Resolution** (paid_social_nav/core/tenants.py:1-45):
- `get_tenant(tenant_id)` loads tenant configuration
- Routes data to tenant-specific GCP project and BigQuery dataset

### Report Generation

**Current Capabilities** (paid_social_nav/render/renderer.py:1-30):
- Markdown rendering with `render_markdown()` function
- Basic template support (noted as "minimal placeholder")
- File output via `write_text()`

**Existing Reports** (reports/ directory):
- `Puttery_Paid_Social_Audit_2025.md` - Full audit report with 66/100 score
- Multiple demographic analysis reports
- Markdown-only format

**Gaps**:
- ❌ HTML report generation not implemented
- ❌ Google Slides integration not implemented
- ⚠️ Template system is minimal (comment suggests Jinja2 upgrade needed)

### Best Practices Documentation

**Research Document** (thoughts/shared/research/2025-11-14-social-media-client-audit-performance.md):
- Comprehensive audit checklist for new clients
- 13-field insight record schema
- Performance metrics across 6 dimensions
- Platform integration requirements

**Implementation Plan** (thoughts/shared/plans/2025-11-14-open-questions-recommendations.md):
- Phase 1: SQL infrastructure (v_budget_concentration view)
- Phase 2: Base adapter pattern for multi-platform support
- Phase 3+: Structured logging, test coverage, templates
- Specific recommendations with success criteria

## Recommended Implementation Approach

### Architecture: Claude Skills as Workflow Orchestrator

Build Claude skills following the existing CLI pattern structure:

```
paid_social_nav/
├── skills/
│   ├── __init__.py
│   ├── base.py              # BaseSkill abstract class
│   └── audit_workflow.py     # AuditWorkflowSkill implementation
├── render/
│   ├── renderer.py           # Extend for HTML + Slides
│   ├── templates/
│   │   ├── audit.md.j2       # Markdown template
│   │   ├── audit.html.j2     # HTML template (new)
│   │   └── slides_deck.py    # Slides structure (new)
└── cli/
    └── main.py               # Add skills_app command group
```

### Implementation Phases

#### Phase 1: HTML Report Generation

Extend existing render module:

**File**: paid_social_nav/render/renderer.py
- Add `render_html(template_name, data)` function
- Integrate Jinja2 for proper templating (replace minimal placeholder)
- Create audit.html.j2 template with charts using Chart.js or similar

**Dependencies to add** (pyproject.toml):
- `jinja2` - Template engine
- `markdown2` - Convert Markdown to HTML if needed

#### Phase 2: Google Slides Integration

Create new module for Slides API:

**File**: paid_social_nav/render/slides.py
- `SlidesClient` class wrapping Google Slides API
- `create_presentation(title, data)` - Creates new presentation
- `add_title_slide()`, `add_insights_slide()`, `add_chart_slide()` - Slide builders
- `export_to_slides(audit_result, tenant_name)` - Main entry point

**Dependencies to add**:
- `google-api-python-client` - Google Slides API
- `google-auth-oauthlib` - Authentication
- `matplotlib` or `plotly` - Chart generation before uploading to Slides

**Authentication**: Store Google OAuth credentials in GCP Secret Manager per tenant

#### Phase 3: Claude Skills Orchestration Layer

Create skills framework:

**File**: paid_social_nav/skills/base.py
```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict

@dataclass
class SkillResult:
    success: bool
    data: Dict[str, Any]
    message: str
    next_step: str | None = None

class BaseSkill(ABC):
    """Base class for Claude skills that orchestrate multi-step workflows"""

    @abstractmethod
    def execute(self, context: Dict[str, Any]) -> SkillResult:
        """Execute the skill workflow"""
        pass

    def validate_context(self, context: Dict[str, Any]) -> bool:
        """Validate required context parameters"""
        return True
```

**File**: paid_social_nav/skills/audit_workflow.py
```python
from .base import BaseSkill, SkillResult
from ..audit.engine import run_audit
from ..render.renderer import render_markdown, render_html
from ..render.slides import export_to_slides

class AuditWorkflowSkill(BaseSkill):
    """Complete audit workflow: config → audit → reports → slides"""

    def execute(self, context: Dict[str, Any]) -> SkillResult:
        # Step 1: Validate tenant exists
        tenant = get_tenant(context['tenant_id'])
        if not tenant:
            return SkillResult(False, {}, f"Tenant {context['tenant_id']} not found")

        # Step 2: Run audit
        audit_result = run_audit(context['audit_config'])

        # Step 3: Generate Markdown report
        md_path = render_markdown('audit.md.j2', {
            'tenant': tenant,
            'result': audit_result,
            'date': datetime.now()
        })

        # Step 4: Generate HTML report
        html_path = render_html('audit.html.j2', {
            'tenant': tenant,
            'result': audit_result
        })

        # Step 5: Generate insights with Claude analysis
        insights = self._generate_insights(audit_result)

        # Step 6: Export to Google Slides
        slides_url = export_to_slides(audit_result, tenant.id, insights)

        return SkillResult(True, {
            'audit_score': audit_result.overall_score,
            'markdown_report': md_path,
            'html_report': html_path,
            'slides_url': slides_url
        }, f"Audit complete: {audit_result.overall_score}/100")

    def _generate_insights(self, audit_result: AuditResult) -> Dict[str, Any]:
        """Use Claude to analyze audit results and generate strategic insights"""
        # Call Claude API to analyze rule results and generate:
        # - Key strengths
        # - Critical issues
        # - Strategic recommendations
        # - Quick wins
        # - Medium/long-term roadmap
        pass
```

**File**: paid_social_nav/cli/main.py (extend):
```python
skills_app = typer.Typer(help="Claude skills automation workflows")

@skills_app.command("audit")
def run_audit_skill(
    tenant_id: str = typer.Option(..., help="Tenant identifier"),
    audit_config: str = typer.Option(..., help="Path to audit YAML config"),
    output_dir: str = typer.Option("reports/", help="Output directory for reports"),
    generate_slides: bool = typer.Option(True, help="Generate Google Slides presentation")
):
    """Run complete audit workflow using Claude skills"""
    skill = AuditWorkflowSkill()
    result = skill.execute({
        'tenant_id': tenant_id,
        'audit_config': audit_config,
        'output_dir': output_dir,
        'generate_slides': generate_slides
    })

    if result.success:
        typer.echo(f"✅ {result.message}")
        typer.echo(f"Markdown: {result.data['markdown_report']}")
        typer.echo(f"HTML: {result.data['html_report']}")
        typer.echo(f"Slides: {result.data['slides_url']}")
    else:
        typer.echo(f"❌ {result.message}", err=True)
        raise typer.Exit(1)

app.add_typer(skills_app, name="skills")
```

#### Phase 4: AI-Generated Insights

Integrate Claude API for strategic analysis:

**File**: paid_social_nav/insights/generator.py
```python
import anthropic
from ..audit.engine import AuditResult

class InsightsGenerator:
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)

    def generate_strategy(self, audit_result: AuditResult, tenant_name: str) -> Dict[str, Any]:
        """Generate strategic insights from audit results using Claude"""

        prompt = f"""Analyze this paid social audit for {tenant_name}:

Overall Score: {audit_result.overall_score}/100

Rule Results:
{self._format_rules(audit_result.rules)}

Provide:
1. Top 3 strengths
2. Top 3 critical issues
3. 5 strategic recommendations with expected impact
4. Quick wins (actionable this week)
5. 90-day roadmap
"""

        response = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )

        return self._parse_insights(response.content)
```

### Storage for Results

**Already implemented**: BigQuery storage via paid_social_nav/storage/bq.py

To store audit results:
1. Create new table `audit_results` with schema:
   - audit_id, tenant_id, run_date, overall_score, rules (JSON), insights (JSON)
2. Add `save_audit_result()` function to storage/bq.py
3. Call after audit completion in workflow skill

### Integration with Existing Workflow

The beauty of this approach is it **leverages existing infrastructure**:

```bash
# Step 1: Add customer (existing tenant system)
vim configs/tenants.yaml  # Add new tenant entry

# Step 2: Run data sync (existing sync command)
psn meta sync-insights --tenant new_customer --account-id act_xxxxx

# Step 3: Run audit workflow (NEW skills command)
psn skills audit --tenant-id new_customer --audit-config configs/audit_new_customer.yaml

# This single command now:
# - Runs audit analysis
# - Generates Markdown report
# - Generates HTML report
# - Creates Google Slides with insights
# - Stores results in BigQuery
```

## Code References

### Core Components
- `paid_social_nav/audit/engine.py:60-331` - AuditEngine class
- `paid_social_nav/audit/rules.py:1-200` - Scoring rules
- `paid_social_nav/core/tenants.py:15-45` - Tenant management
- `paid_social_nav/cli/main.py:244-290` - Audit CLI command
- `paid_social_nav/render/renderer.py:7-30` - Report rendering

### Configuration
- `configs/tenants.yaml` - Tenant definitions
- `configs/audit_puttery.yaml` - Audit configuration example
- `configs/audit_test.yaml` - Test configuration

### Storage
- `paid_social_nav/storage/bq.py:1-200` - BigQuery client
- `sql/views/v_budget_concentration.sql` - Budget concentration view
- `sql/views/v_creative_mix.sql` - Creative diversity view

## Architecture Benefits

This approach provides:

1. **Consistency**: Follows existing CLI pattern and adapter structure
2. **Reusability**: Each skill step can be called independently
3. **Extensibility**: Easy to add new skills for other workflows
4. **Testability**: Each component can be unit tested
5. **Observability**: Leverages existing structured logging
6. **Multi-tenancy**: Built on existing tenant management system

## Dependencies to Add

**pyproject.toml additions**:
```toml
[project]
dependencies = [
    # Existing...
    "jinja2>=3.1.0",              # Template engine
    "google-api-python-client>=2.0.0",  # Google Slides API
    "google-auth-oauthlib>=1.0.0",      # Google OAuth
    "anthropic>=0.34.0",                 # Claude API client
    "matplotlib>=3.7.0",                 # Chart generation
]
```

## Replication to Other Repos

To replicate this pattern to other repositories:

1. **Extract skills framework** into standalone package:
   - `paid_social_nav/skills/base.py` → `claude_skills/base.py`
   - Make pip-installable: `pip install claude-skills`

2. **Create skill templates**:
   - Document BaseSkill interface
   - Provide cookiecutter template for new skills
   - Share render/slides modules as reusable components

3. **Standardize configuration**:
   - YAML-based skill definitions
   - Environment variable patterns (PSN_* prefix pattern)
   - Secret management via GCP Secret Manager

4. **Share CLI patterns**:
   - Typer-based command structure
   - Consistent parameter naming
   - Error handling and logging standards

## Historical Context (from thoughts/)

- `thoughts/shared/research/2025-11-14-social-media-client-audit-performance.md` - Comprehensive audit checklist and performance improvement strategies
- `thoughts/shared/plans/2025-11-14-open-questions-recommendations.md` - Implementation plan for missing infrastructure (SQL views, base adapter pattern, templates)

## Next Steps

1. **Immediate**:
   - Create skills/ directory structure
   - Implement BaseSkill abstract class
   - Add Jinja2 and upgrade render module

2. **Short-term (1-2 weeks)**:
   - Implement HTML report generation with templates
   - Build Google Slides integration
   - Create AuditWorkflowSkill

3. **Medium-term (3-4 weeks)**:
   - Integrate Claude API for insights generation
   - Add audit results storage to BigQuery
   - Create comprehensive skill tests

4. **Long-term**:
   - Extract skills framework for reuse
   - Build additional skills (competitive analysis, recommendation engine)
   - Create skill marketplace/registry

## Open Questions

1. **Claude API usage**: Should insights generation use Claude API or Claude Code's built-in capabilities?
2. **Google Slides templates**: Should we create reusable presentation templates or generate dynamically?
3. **Skill chaining**: Should skills be chainable (output of one feeds into next)?
4. **Versioning**: How to version skill definitions and track schema changes?
