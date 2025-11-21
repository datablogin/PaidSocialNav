from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, TemplateNotFound

from .. import __version__
from ..core.logging_config import get_logger

logger = get_logger(__name__)


class ReportRenderer:
    """Renders audit reports using Jinja2 templates."""

    def __init__(self, templates_dir: Path | None = None):
        if templates_dir is None:
            templates_dir = Path(__file__).parent / "templates"
        # Use select_autoescape to automatically escape HTML but not Markdown
        self.env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=lambda name: name is not None and name.endswith('.html.j2'),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render_markdown(self, data: dict[str, Any]) -> str:
        """Render Markdown report from audit data.

        Args:
            data: Dictionary containing report data with required keys:
                  tenant_name, period, audit_date, overall_score, rules, recommendations

        Returns:
            Rendered Markdown string

        Raises:
            TemplateNotFound: If the Markdown template is missing
            RuntimeError: If template rendering fails
        """
        try:
            template = self.env.get_template("audit_report.md.j2")
            logger.debug("Rendering Markdown report", extra={"tenant": data.get("tenant_name")})
            return template.render(**data, version=__version__)
        except TemplateNotFound as e:
            logger.error("Markdown template not found", extra={"error": str(e)})
            raise RuntimeError(
                f"Markdown template not found: {e}. "
                "Ensure paid_social_nav/render/templates/audit_report.md.j2 exists."
            ) from e
        except Exception as e:
            logger.error("Failed to render Markdown report", extra={"error": str(e)})
            raise RuntimeError(f"Failed to render Markdown report: {e}") from e

    def render_html(self, data: dict[str, Any]) -> str:
        """Render HTML report from audit data.

        Args:
            data: Dictionary containing report data with required keys:
                  tenant_name, period, audit_date, overall_score, rules, recommendations

        Returns:
            Rendered HTML string with embedded Chart.js visualizations

        Raises:
            TemplateNotFound: If the HTML template is missing
            RuntimeError: If template rendering fails
        """
        try:
            template = self.env.get_template("audit_report.html.j2")
            logger.debug("Rendering HTML report", extra={"tenant": data.get("tenant_name")})
            return template.render(**data, version=__version__)
        except TemplateNotFound as e:
            logger.error("HTML template not found", extra={"error": str(e)})
            raise RuntimeError(
                f"HTML template not found: {e}. "
                "Ensure paid_social_nav/render/templates/audit_report.html.j2 exists."
            ) from e
        except Exception as e:
            logger.error("Failed to render HTML report", extra={"error": str(e)})
            raise RuntimeError(f"Failed to render HTML report: {e}") from e


def render_markdown(templates_dir: Path, data: dict) -> str:
    """Legacy function for backward compatibility."""
    renderer = ReportRenderer(templates_dir)
    return renderer.render_markdown(data)


def write_text(path: str, content: str) -> None:
    """Write text content to file."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
