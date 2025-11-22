"""Chart generation utilities for audit reports."""

from __future__ import annotations

import base64
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
        # Find creative_diversity rules and extract shares
        creative_rules = [r for r in rules if r.get("rule") == "creative_diversity"]

        if not creative_rules:
            logger.debug("No creative diversity data found, skipping chart")
            return {}

        # Average across windows if multiple
        video_shares = []
        image_shares = []

        for rule in creative_rules:
            findings = rule.get("findings", {})
            video_share = findings.get("video_share", 0.0)
            image_share = findings.get("image_share", 0.0)

            if video_share or image_share:
                video_shares.append(video_share)
                image_shares.append(image_share)

        if not video_shares and not image_shares:
            logger.debug("No creative mix data available")
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
            colors.append("#667eea")

        if avg_image > 0:
            labels.append(f"Image ({avg_image * 100:.1f}%)")
            sizes.append(avg_image)
            colors.append("#764ba2")

        if other > 0:
            labels.append(f"Other ({other * 100:.1f}%)")
            sizes.append(other)
            colors.append("#cccccc")

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
        # Find pacing_vs_target rules
        pacing_rules = [r for r in rules if r.get("rule") == "pacing_vs_target"]

        if not pacing_rules:
            logger.debug("No pacing data found, skipping chart")
            return {}

        windows = []
        actuals = []
        targets = []

        for rule in pacing_rules:
            findings = rule.get("findings", {})
            actual = findings.get("actual", 0.0)
            target = findings.get("target", 0.0)

            if target > 0:  # Only include windows with target set
                windows.append(rule.get("window", "unknown"))
                actuals.append(actual)
                targets.append(target)

        if not windows:
            logger.debug("No pacing data with targets available")
            return {}

        # Create grouped bar chart
        x = np.arange(len(windows))
        width = 0.35

        fig, ax = plt.subplots(figsize=(8, 5))

        bars1 = ax.bar(x - width / 2, actuals, width, label="Actual Spend", color="#667eea")
        bars2 = ax.bar(x + width / 2, targets, width, label="Target Spend", color="#764ba2")

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
        # Extract CTR and frequency data
        ctr_rules = [r for r in rules if r.get("rule") == "ctr_threshold"]
        freq_rules = [r for r in rules if r.get("rule") == "frequency_threshold"]

        if not ctr_rules and not freq_rules:
            logger.debug("No performance trend data found, skipping chart")
            return {}

        # Organize by window
        window_data: dict[str, dict[str, float]] = {}

        for rule in ctr_rules:
            window = rule.get("window", "unknown")
            findings = rule.get("findings", {})
            ctr = findings.get("ctr", 0.0)
            if window not in window_data:
                window_data[window] = {}
            window_data[window]["ctr"] = ctr * 100  # Convert to percentage

        for rule in freq_rules:
            window = rule.get("window", "unknown")
            findings = rule.get("findings", {})
            freq = findings.get("frequency", 0.0)
            if window not in window_data:
                window_data[window] = {}
            window_data[window]["frequency"] = freq

        if not window_data:
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
            color1 = "#667eea"
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
            color2 = "#764ba2"
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

        # Group by rule name and average scores across windows
        rule_scores: dict[str, list[float]] = {}

        for rule in rules:
            rule_name = rule.get("rule", "unknown")
            score = rule.get("score", 0.0)

            if rule_name not in rule_scores:
                rule_scores[rule_name] = []
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

        # Color bars based on score
        colors = []
        for score in avg_scores:
            if score >= 80:
                colors.append("#4caf50")  # Green
            elif score >= 60:
                colors.append("#ffc107")  # Yellow
            elif score >= 40:
                colors.append("#ff9800")  # Orange
            else:
                colors.append("#f44336")  # Red

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

        plt.close(fig)
        return result
