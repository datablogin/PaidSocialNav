"""Chart generation and visualization utilities for audit reports.

This module provides utilities for generating professional-grade matplotlib charts that
visualize the results of paid social media advertising audits. It enables rendering of
complex audit metrics into clear, interpretable visual formats suitable for client reports
and stakeholder presentations.

Supported chart types: pie charts for creative distribution, bar charts for budget pacing
analysis, line charts for performance trends, and horizontal bar charts for rule-based scoring.
Charts can be saved to disk as PNG files and/or embedded as base64-encoded data URIs.

Chart Generation Process:
1. Create ChartGenerator instance with optional output directory and DPI settings
2. Call appropriate chart generation method with audit rule results
3. Method extracts relevant data, calculates aggregations, and constructs visualization
4. Charts rendered using matplotlib with configurable styling and layout
5. Charts saved to file (if output_dir specified) and encoded as base64 strings

Usage:
    from pathlib import Path
    from paid_social_nav.visuals.charts import ChartGenerator

    generator = ChartGenerator(output_dir=Path("./output"), dpi=150)
    creative = generator.generate_creative_mix_chart(
        rules=audit_results['rules'],
        tenant_name="client_name"
    )
    print(f"Chart saved: {creative.get('path')}")
    print(f"Base64 size: {len(creative.get('base64', ''))} bytes")

Architecture Notes:
    - Uses matplotlib 'Agg' backend for server-side rendering
    - Responsive figure sizing based on data complexity
    - Handles missing data gracefully with debug logging
    - Base64 encoding for web embedding
    - Color-coded visualizations (green/yellow/orange/red scoring)
    - Automatic figure cleanup to prevent memory leaks

Performance Notes:
    - Base64 encoding adds ~33% overhead to PNG binary size
    - Consider caching charts for repeated audit results
    - DPI setting affects file size and quality
    - Each chart generation creates temporary figure in memory
"""

from __future__ import annotations

import base64
from collections import defaultdict
from io import BytesIO
from pathlib import Path
from typing import Any

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

from ..core.logging_config import get_logger

# Use non-interactive backend for server environments
matplotlib.use("Agg")

logger = get_logger(__name__)


# Score threshold constants for performance scoring
SCORE_EXCELLENT_THRESHOLD = 80
SCORE_GOOD_THRESHOLD = 60
SCORE_FAIR_THRESHOLD = 40

# Color constants for score distribution visualization
COLOR_EXCELLENT = "#4caf50"  # Green
COLOR_GOOD = "#ffc107"  # Yellow
COLOR_FAIR = "#ff9800"  # Orange
COLOR_POOR = "#f44336"  # Red

# Color constants for creative mix and performance charts
COLOR_VIDEO = "#667eea"  # Blue/Purple
COLOR_IMAGE = "#764ba2"  # Dark Purple
COLOR_OTHER = "#cccccc"  # Light Gray


class ChartGenerator:
    """Generate charts for audit reports using matplotlib."""

    def __init__(self, output_dir: Path | None = None, dpi: int = 100):
        """Initialize chart generator.

        Args:
            output_dir: Optional directory to save chart images. If None, charts are only returned as base64.
            dpi: Resolution for chart images (default: 100)
        """
        self.output_dir = output_dir
        self.dpi = dpi
        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)

    def generate_creative_mix_chart(
        self, rules: list[dict[str, Any]], tenant_name: str = "report"
    ) -> dict[str, str]:
        """Generate creative mix pie chart showing video vs image share.

        Args:
            rules: List of rule results from audit
            tenant_name: Tenant name for file naming

        Returns:
            Dict with 'path' (if output_dir set) and 'base64' keys
        """
        # Single-pass iteration: collect and aggregate shares in one pass
        video_shares = []
        image_shares = []

        for rule in rules:
            if rule.get("rule") != "creative_diversity":
                continue

            findings = rule.get("findings", {})
            video_share = findings.get("video_share", 0.0)
            image_share = findings.get("image_share", 0.0)

            if video_share or image_share:
                video_shares.append(video_share)
                image_shares.append(image_share)

        if not video_shares and not image_shares:
            logger.debug("No creative diversity data found, skipping chart")
            return {}

        avg_video = np.mean(video_shares) if video_shares else 0.0
        avg_image = np.mean(image_shares) if image_shares else 0.0
        other = max(0.0, 1.0 - avg_video - avg_image)

        # Create pie chart
        fig, ax = plt.subplots(figsize=(6, 6))

        labels = []
        sizes = []
        colors = []

        if avg_video > 0:
            labels.append(f"Video ({avg_video * 100:.1f}%)")
            sizes.append(avg_video)
            colors.append(COLOR_VIDEO)

        if avg_image > 0:
            labels.append(f"Image ({avg_image * 100:.1f}%)")
            sizes.append(avg_image)
            colors.append(COLOR_IMAGE)

        if other > 0:
            labels.append(f"Other ({other * 100:.1f}%)")
            sizes.append(other)
            colors.append(COLOR_OTHER)

        if not sizes:
            plt.close(fig)
            return {}

        ax.pie(sizes, labels=labels, colors=colors, autopct="", startangle=90)
        ax.set_title("Creative Mix Distribution", fontsize=14, fontweight="bold")

        return self._save_chart(fig, f"{tenant_name}_creative_mix")

    def generate_pacing_chart(
        self, rules: list[dict[str, Any]], tenant_name: str = "report"
    ) -> dict[str, str]:
        """Generate pacing vs budget bar chart.

        Args:
            rules: List of rule results from audit
            tenant_name: Tenant name for file naming

        Returns:
            Dict with 'path' (if output_dir set) and 'base64' keys
        """
        # Single-pass iteration: collect pacing data in one pass
        windows = []
        actuals = []
        targets = []

        for rule in rules:
            if rule.get("rule") != "pacing_vs_target":
                continue

            findings = rule.get("findings", {})
            actual = findings.get("actual", 0.0)
            target = findings.get("target", 0.0)

            if target > 0:  # Only include windows with target set
                windows.append(rule.get("window", "unknown"))
                actuals.append(actual)
                targets.append(target)

        if not windows:
            logger.debug("No pacing data found, skipping chart")
            return {}

        # Create grouped bar chart
        x = np.arange(len(windows))
        width = 0.35

        fig, ax = plt.subplots(figsize=(8, 5))

        bars1 = ax.bar(x - width / 2, actuals, width, label="Actual Spend", color=COLOR_VIDEO)
        bars2 = ax.bar(x + width / 2, targets, width, label="Target Spend", color=COLOR_IMAGE)

        ax.set_xlabel("Time Window", fontsize=11)
        ax.set_ylabel("Spend ($)", fontsize=11)
        ax.set_title("Budget Pacing vs Target", fontsize=14, fontweight="bold")
        ax.set_xticks(x)
        ax.set_xticklabels(windows, rotation=45, ha="right")
        ax.legend()
        ax.grid(axis="y", alpha=0.3)

        # Add value labels on bars
        for bars in [bars1, bars2]:
            for bar in bars:
                height = bar.get_height()
                if height > 0:
                    ax.text(
                        bar.get_x() + bar.get_width() / 2.0,
                        height,
                        f"${height:,.0f}",
                        ha="center",
                        va="bottom",
                        fontsize=8,
                    )

        plt.tight_layout()
        return self._save_chart(fig, f"{tenant_name}_pacing")

    def generate_performance_trends_chart(
        self, rules: list[dict[str, Any]], tenant_name: str = "report"
    ) -> dict[str, str]:
        """Generate performance trends line chart (CTR and Frequency over time).

        Args:
            rules: List of rule results from audit
            tenant_name: Tenant name for file naming

        Returns:
            Dict with 'path' (if output_dir set) and 'base64' keys
        """
        # Single-pass iteration: process all rules once, organizing by window and type
        window_data: dict[str, dict[str, float]] = defaultdict(dict)
        has_any_data = False

        for rule in rules:
            rule_type = rule.get("rule")
            if rule_type not in ("ctr_threshold", "frequency_threshold"):
                continue

            has_any_data = True
            window = rule.get("window", "unknown")
            findings = rule.get("findings", {})

            if rule_type == "ctr_threshold":
                ctr = findings.get("ctr", 0.0)
                window_data[window]["ctr"] = ctr * 100  # Convert to percentage
            elif rule_type == "frequency_threshold":
                freq = findings.get("frequency", 0.0)
                window_data[window]["frequency"] = freq

        if not has_any_data or not window_data:
            logger.debug("No performance trend data found, skipping chart")
            return {}

        # Sort windows (basic alphabetical for now)
        sorted_windows = sorted(window_data.keys())

        ctrs = [window_data[w].get("ctr", 0.0) for w in sorted_windows]
        freqs = [window_data[w].get("frequency", 0.0) for w in sorted_windows]

        # Only plot if we have data
        has_ctr = any(c > 0 for c in ctrs)
        has_freq = any(f > 0 for f in freqs)

        if not has_ctr and not has_freq:
            return {}

        fig, ax1 = plt.subplots(figsize=(8, 5))

        x = np.arange(len(sorted_windows))

        # Plot CTR on left axis
        if has_ctr:
            color1 = COLOR_VIDEO
            ax1.set_xlabel("Time Window", fontsize=11)
            ax1.set_ylabel("CTR (%)", color=color1, fontsize=11)
            line1 = ax1.plot(
                x, ctrs, color=color1, marker="o", linewidth=2, label="CTR"
            )
            ax1.tick_params(axis="y", labelcolor=color1)
            ax1.grid(axis="y", alpha=0.3)

        # Plot Frequency on right axis
        ax2 = ax1.twinx() if has_freq else None
        if has_freq and ax2:
            color2 = COLOR_IMAGE
            ax2.set_ylabel("Frequency", color=color2, fontsize=11)
            line2 = ax2.plot(
                x, freqs, color=color2, marker="s", linewidth=2, label="Frequency"
            )
            ax2.tick_params(axis="y", labelcolor=color2)

        ax1.set_xticks(x)
        ax1.set_xticklabels(sorted_windows, rotation=45, ha="right")
        ax1.set_title("Performance Trends", fontsize=14, fontweight="bold")

        # Combined legend
        lines = []
        labels = []
        if has_ctr:
            lines.extend(line1)
            labels.append("CTR")
        if has_freq and ax2:
            lines.extend(line2)
            labels.append("Frequency")

        if lines:
            ax1.legend(lines, labels, loc="upper left")

        plt.tight_layout()
        return self._save_chart(fig, f"{tenant_name}_performance_trends")

    def generate_score_distribution_chart(
        self, rules: list[dict[str, Any]], tenant_name: str = "report"
    ) -> dict[str, str]:
        """Generate horizontal bar chart showing scores by rule.

        Args:
            rules: List of rule results from audit
            tenant_name: Tenant name for file naming

        Returns:
            Dict with 'path' (if output_dir set) and 'base64' keys
        """
        if not rules:
            return {}

        # Single-pass iteration with defaultdict to avoid repeated dictionary checks
        rule_scores: dict[str, list[float]] = defaultdict(list)

        for rule in rules:
            rule_name = rule.get("rule", "unknown")
            score = rule.get("score", 0.0)
            rule_scores[rule_name].append(score)

        # Calculate average score per rule
        rule_names = []
        avg_scores = []

        for rule_name, scores in sorted(rule_scores.items()):
            rule_names.append(rule_name.replace("_", " ").title())
            avg_scores.append(np.mean(scores))

        if not rule_names:
            return {}

        # Create horizontal bar chart
        fig, ax = plt.subplots(figsize=(8, len(rule_names) * 0.5 + 2))

        # Color bars based on score - single pass with list comprehension
        colors = [
            COLOR_EXCELLENT if score >= SCORE_EXCELLENT_THRESHOLD
            else COLOR_GOOD if score >= SCORE_GOOD_THRESHOLD
            else COLOR_FAIR if score >= SCORE_FAIR_THRESHOLD
            else COLOR_POOR
            for score in avg_scores
        ]

        y_pos = np.arange(len(rule_names))
        bars = ax.barh(y_pos, avg_scores, color=colors, alpha=0.8)

        ax.set_yticks(y_pos)
        ax.set_yticklabels(rule_names)
        ax.set_xlabel("Score", fontsize=11)
        ax.set_title("Rule Scores Distribution", fontsize=14, fontweight="bold")
        ax.set_xlim(0, 100)
        ax.grid(axis="x", alpha=0.3)

        # Add score labels
        for bar, score in zip(bars, avg_scores, strict=True):
            ax.text(
                float(score + 2),
                bar.get_y() + bar.get_height() / 2,
                f"{score:.1f}",
                va="center",
                fontsize=9,
            )

        plt.tight_layout()
        return self._save_chart(fig, f"{tenant_name}_score_distribution")

    def _save_chart(self, fig: plt.Figure, filename: str) -> dict[str, str]:
        """Save chart to file and/or encode as base64.

        Args:
            fig: Matplotlib figure to save
            filename: Base filename (without extension)

        Returns:
            Dict with 'path' and/or 'base64' keys
        """
        try:
            result = {}

            # Save to file if output_dir is set
            if self.output_dir:
                filepath = self.output_dir / f"{filename}.png"
                try:
                    fig.savefig(filepath, dpi=self.dpi, bbox_inches="tight", format="png")
                    result["path"] = str(filepath)
                    logger.debug(f"Chart saved to {filepath}")
                except (OSError, ValueError) as e:
                    logger.warning(f"Failed to save chart to {filepath}: {e}")

            # Always generate base64 for embedding
            try:
                buffer = BytesIO()
                fig.savefig(buffer, dpi=self.dpi, bbox_inches="tight", format="png")
                buffer.seek(0)
                img_base64 = base64.b64encode(buffer.read()).decode("utf-8")
                result["base64"] = img_base64
                buffer.close()
            except (OSError, ValueError) as e:
                logger.warning(f"Failed to generate base64 for chart: {e}")

            return result
        finally:
            # Ensure figure is always closed to prevent memory leaks
            plt.close(fig)
