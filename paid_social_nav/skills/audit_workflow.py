from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from ..audit.engine import run_audit
from ..core.logging_config import get_logger
from ..core.tenants import get_tenant
from ..insights.generator import InsightsGenerator
from ..render.renderer import ReportRenderer, write_text
from .base import BaseSkill, SkillResult

logger = get_logger(__name__)


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
        """Validate required parameters and paths."""
        if "tenant_id" not in context:
            return False, "Missing required parameter: tenant_id"
        if "audit_config" not in context:
            return False, "Missing required parameter: audit_config"

        config_path = Path(context["audit_config"])
        if not config_path.exists():
            return False, f"Audit config not found: {config_path}"

        # Validate output_dir if provided
        if "output_dir" in context:
            output_dir = Path(context["output_dir"])
            # Prevent path traversal attacks
            try:
                output_dir = output_dir.resolve()
                # Check if path contains suspicious patterns
                if ".." in str(output_dir):
                    return False, f"Invalid output directory (path traversal detected): {output_dir}"
            except (OSError, RuntimeError) as e:
                return False, f"Invalid output directory path: {e}"

        return True, ""

    def execute(self, context: dict[str, Any]) -> SkillResult:
        """Execute the complete audit workflow."""
        logger.info(
            "Starting audit workflow",
            extra={
                "tenant_id": context.get("tenant_id"),
                "audit_config": context.get("audit_config")
            }
        )

        # Step 1: Validate context
        is_valid, error_msg = self.validate_context(context)
        if not is_valid:
            logger.error("Context validation failed", extra={"error": error_msg})
            return SkillResult(
                success=False,
                data={},
                message=error_msg
            )

        # Step 2: Validate tenant exists
        tenant = get_tenant(context["tenant_id"])
        if not tenant:
            error_msg = f"Tenant '{context['tenant_id']}' not found in configs/tenants.yaml"
            logger.error("Tenant not found", extra={"tenant_id": context["tenant_id"]})
            return SkillResult(
                success=False,
                data={},
                message=error_msg
            )

        # Step 3: Run audit
        try:
            audit_result = run_audit(context["audit_config"])
            logger.info(
                "Audit completed",
                extra={
                    "tenant_id": tenant.id,
                    "overall_score": audit_result.overall_score
                }
            )
        except (RuntimeError, ValueError, OSError) as e:
            # RuntimeError: BigQuery errors, ValueError: Config validation, OSError: File I/O
            logger.error(
                "Audit execution failed",
                extra={
                    "tenant_id": tenant.id,
                    "error": str(e),
                    "config": context["audit_config"]
                },
                exc_info=True
            )
            return SkillResult(
                success=False,
                data={},
                message=f"Audit failed: {e}"
            )

        # Step 3.5: Generate AI insights if Claude API key is available
        insights = None
        claude_api_key = os.getenv("ANTHROPIC_API_KEY")
        if claude_api_key:
            try:
                generator = InsightsGenerator(claude_api_key)
                insights = generator.generate_strategy(audit_result, tenant.id)
            except Exception as e:
                # Log error but continue - insights are optional enhancement
                logger.warning(
                    "Failed to generate AI insights, continuing without them",
                    extra={"error": str(e)}
                )

        # Step 4: Load config and prepare report data
        try:
            config_path = Path(context["audit_config"])
            cfg = yaml.safe_load(config_path.read_text())
            windows = cfg.get("windows", [])

            # Calculate period from windows
            if windows and isinstance(windows, list) and len(windows) > 0:
                valid_windows = [w for w in windows if w]
                period = ", ".join(str(w) for w in valid_windows) if valid_windows else datetime.now().strftime("%Y")
            else:
                period = datetime.now().strftime("%Y")

        except (yaml.YAMLError, OSError, KeyError) as e:
            # YAMLError: Invalid YAML, OSError: File I/O, KeyError: Missing windows key
            logger.warning(
                "Failed to load config for period calculation, using current year",
                extra={"error": str(e)}
            )
            period = datetime.now().strftime("%Y")

        data = {
            "tenant_name": tenant.id,
            "period": period,
            "audit_date": datetime.now().strftime("%Y-%m-%d"),
            "overall_score": audit_result.overall_score,
            "rules": audit_result.rules,
            "recommendations": insights.get("recommendations", []) if insights else [],
            "strengths": insights.get("strengths", []) if insights else [],
            "issues": insights.get("issues", []) if insights else [],
            "quick_wins": insights.get("quick_wins", []) if insights else [],
            "roadmap": insights.get("roadmap", {}) if insights else {},
        }

        # Step 5: Generate reports
        output_dir = Path(context.get("output_dir", "reports"))
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error(
                "Failed to create output directory",
                extra={"output_dir": str(output_dir), "error": str(e)}
            )
            return SkillResult(
                success=False,
                data={},
                message=f"Failed to create output directory: {e}"
            )

        renderer = ReportRenderer()

        # Generate Markdown
        md_path = output_dir / f"{tenant.id}_audit_{datetime.now().strftime('%Y%m%d')}.md"
        try:
            md_content = renderer.render_markdown(data)
            write_text(str(md_path), md_content)
            logger.info("Markdown report generated", extra={"path": str(md_path)})
        except (OSError, RuntimeError) as e:
            # OSError: File I/O errors, RuntimeError: Template rendering errors
            logger.error(
                "Failed to generate Markdown report",
                extra={"path": str(md_path), "error": str(e)},
                exc_info=True
            )
            return SkillResult(
                success=False,
                data={},
                message=f"Failed to generate Markdown report: {e}"
            )

        # Generate HTML
        html_path = output_dir / f"{tenant.id}_audit_{datetime.now().strftime('%Y%m%d')}.html"
        try:
            html_content = renderer.render_html(data)
            write_text(str(html_path), html_content)
            logger.info("HTML report generated", extra={"path": str(html_path)})
        except (OSError, RuntimeError) as e:
            # OSError: File I/O errors, RuntimeError: Template rendering errors
            logger.error(
                "Failed to generate HTML report",
                extra={"path": str(html_path), "error": str(e)},
                exc_info=True
            )
            return SkillResult(
                success=False,
                data={},
                message=f"Failed to generate HTML report: {e}"
            )

        # Step 6: Return results
        logger.info(
            "Audit workflow completed successfully",
            extra={
                "tenant_id": tenant.id,
                "score": audit_result.overall_score,
                "markdown_report": str(md_path),
                "html_report": str(html_path)
            }
        )
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
