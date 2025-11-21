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
        """Render HTML report from audit data.

        Note: HTML template will be available in Phase 2.
        """
        try:
            template = self.env.get_template("audit_report.html.j2")
            return template.render(**data, version=__version__)
        except Exception as e:
            raise NotImplementedError(
                "HTML template not available in Phase 1. "
                "Use render_markdown() for Markdown reports. "
                "HTML rendering will be added in Phase 2."
            ) from e


def render_markdown(templates_dir: Path, data: dict) -> str:
    """Legacy function for backward compatibility."""
    renderer = ReportRenderer(templates_dir)
    return renderer.render_markdown(data)


def write_text(path: str, content: str) -> None:
    """Write text content to file."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
