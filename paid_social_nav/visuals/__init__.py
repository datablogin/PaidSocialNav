"""Visualization package for audit report rendering.

This package provides visualization utilities for generating professional audit reports
from paid social media advertising audits. It acts as the presentation layer that transforms
raw audit metrics and insights into engaging visual formats for stakeholder communication.

The visualization system is modular and extensible, with the ChartGenerator class handling
matplotlib-based chart creation for various metric types and rendering scenarios.

Key Capabilities:
    1. Chart generation from structured audit results (pie, bar, line charts)
    2. Automatic PNG file creation with configurable DPI and sizing
    3. Base64 encoding for embedding charts in HTML documents
    4. Color-coded visualizations based on performance scores
    5. Responsive figure sizing based on data complexity

Main Components:
    - ChartGenerator: Matplotlib-based chart rendering with file and base64 output

Usage:
    from paid_social_nav.visuals import ChartGenerator
    from pathlib import Path

    generator = ChartGenerator(output_dir=Path("./output"))
    chart = generator.generate_creative_mix_chart(
        rules=audit_results,
        tenant_name="client_name"
    )

Architecture Notes:
    - Charts use non-interactive 'Agg' backend for server environments
    - All chart generation is stateless and parallelizable
    - Memory management includes automatic figure cleanup
    - Design supports future expansion with additional chart types

Integration Notes:
    - Used by the render module for HTML report generation
    - Outputs compatible with modern web standards (PNG, base64)
"""

from __future__ import annotations

from .charts import ChartGenerator

__all__ = ["ChartGenerator"]
