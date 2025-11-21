from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

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
