from __future__ import annotations

from pathlib import Path


def render_markdown(templates_dir: Path, data: dict) -> str:
    # Minimal placeholder renderer for CLI; can be replaced with Jinja2 later
    title = f"Audit Report: {data.get('client', 'Client')} ({data.get('period', '')})"
    return f"# {title}\n\nOverall Score: {data.get('overall_score', 0)}\n"


def write_text(path: str, content: str) -> None:
    p = Path(path)
    p.write_text(content, encoding="utf-8")
