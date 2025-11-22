from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, TemplateNotFound

from .. import __version__
from ..core.logging_config import get_logger
from ..visuals.charts import ChartGenerator

logger = get_logger(__name__)


class ReportRenderer:
    """Renders audit reports using Jinja2 templates."""

    def __init__(
        self, templates_dir: Path | None = None, assets_dir: Path | None = None
    ):
        if templates_dir is None:
            templates_dir = Path(__file__).parent / "templates"
        # Use select_autoescape to automatically escape HTML but not Markdown
        self.env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=lambda name: name is not None and name.endswith(".html.j2"),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.assets_dir = assets_dir
        self.chart_generator = ChartGenerator(output_dir=assets_dir) if assets_dir else None

    def render_markdown(
        self, data: dict[str, Any], generate_charts: bool = True
    ) -> str:
        """Render Markdown report from audit data.

        Args:
            data: Dictionary containing report data with required keys:
                  tenant_name, period, audit_date, overall_score, rules, recommendations
            generate_charts: Whether to generate and embed charts (default: True)

        Returns:
            Rendered Markdown string

        Raises:
            TemplateNotFound: If the Markdown template is missing
            RuntimeError: If template rendering fails
        """
        # Generate charts if enabled
        charts: dict[str, Any] = {}
        evidence: dict[str, Any] = {}

        if generate_charts:
            charts, evidence = self._generate_visuals_and_evidence(data)

        try:
            template = self.env.get_template("audit_report.md.j2")
            logger.debug(
                "Rendering Markdown report", extra={"tenant": data.get("tenant_name")}
            )
            return template.render(
                **data, version=__version__, charts=charts, evidence=evidence
            )
        except TemplateNotFound as e:
            logger.error("Markdown template not found", extra={"error": str(e)})
            raise RuntimeError(
                f"Markdown template not found: {e}. "
                "Ensure paid_social_nav/render/templates/audit_report.md.j2 exists."
            ) from e
        except Exception as e:
            logger.error("Failed to render Markdown report", extra={"error": str(e)})
            raise RuntimeError(f"Failed to render Markdown report: {e}") from e

    def render_html(self, data: dict[str, Any], generate_charts: bool = True) -> str:
        """Render HTML report from audit data.

        Args:
            data: Dictionary containing report data with required keys:
                  tenant_name, period, audit_date, overall_score, rules, recommendations
            generate_charts: Whether to generate and embed charts (default: True)

        Returns:
            Rendered HTML string with embedded Chart.js visualizations

        Raises:
            TemplateNotFound: If the HTML template is missing
            RuntimeError: If template rendering fails
        """
        # Generate charts if enabled
        charts: dict[str, Any] = {}
        evidence: dict[str, Any] = {}

        if generate_charts:
            charts, evidence = self._generate_visuals_and_evidence(data)

        try:
            template = self.env.get_template("audit_report.html.j2")
            logger.debug(
                "Rendering HTML report", extra={"tenant": data.get("tenant_name")}
            )
            return template.render(
                **data, version=__version__, charts=charts, evidence=evidence
            )
        except TemplateNotFound as e:
            logger.error("HTML template not found", extra={"error": str(e)})
            raise RuntimeError(
                f"HTML template not found: {e}. "
                "Ensure paid_social_nav/render/templates/audit_report.html.j2 exists."
            ) from e
        except Exception as e:
            logger.error("Failed to render HTML report", extra={"error": str(e)})
            raise RuntimeError(f"Failed to render HTML report: {e}") from e

    def _generate_visuals_and_evidence(
        self, data: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Generate charts and evidence data for the report.

        Args:
            data: Report data containing rules and other audit information

        Returns:
            Tuple of (charts dict, evidence dict)
        """
        charts = {}
        evidence = {}
        chart_failures = []

        # Always create a basic chart generator for generating charts
        generator = self.chart_generator or ChartGenerator()

        rules = data.get("rules", [])
        tenant_name = data.get("tenant_name", "report")

        # Generate charts individually with error handling for each
        # Creative mix chart
        try:
            creative_chart = generator.generate_creative_mix_chart(rules, tenant_name)
            if creative_chart:
                charts["creative_mix"] = creative_chart
        except Exception as e:
            chart_failures.append(("creative_mix", str(e)))
            logger.warning(f"Failed to generate creative mix chart: {e}", exc_info=True)

        # Pacing chart
        try:
            pacing_chart = generator.generate_pacing_chart(rules, tenant_name)
            if pacing_chart:
                charts["pacing"] = pacing_chart
        except Exception as e:
            chart_failures.append(("pacing", str(e)))
            logger.warning(f"Failed to generate pacing chart: {e}", exc_info=True)

        # Performance trends chart
        try:
            trends_chart = generator.generate_performance_trends_chart(
                rules, tenant_name
            )
            if trends_chart:
                charts["performance_trends"] = trends_chart
        except Exception as e:
            chart_failures.append(("performance_trends", str(e)))
            logger.warning(f"Failed to generate performance trends chart: {e}", exc_info=True)

        # Score distribution chart
        try:
            score_chart = generator.generate_score_distribution_chart(rules, tenant_name)
            if score_chart:
                charts["score_distribution"] = score_chart
        except Exception as e:
            chart_failures.append(("score_distribution", str(e)))
            logger.warning(f"Failed to generate score distribution chart: {e}", exc_info=True)

        # Log summary of chart generation
        if chart_failures:
            logger.warning(
                f"Generated {len(charts)}/4 charts. Failures: {', '.join(f[0] for f in chart_failures)}",
                extra={"tenant": tenant_name, "failures": chart_failures},
            )
        else:
            logger.info(
                f"Successfully generated all {len(charts)} charts for report",
                extra={"tenant": tenant_name},
            )

        # Generate evidence appendix data
        try:
            evidence = self._build_evidence_appendix(data)
            logger.debug("Built evidence appendix", extra={"tenant": tenant_name})
        except Exception as e:
            logger.warning(f"Failed to build evidence appendix: {e}", exc_info=True)

        return charts, evidence

    def _build_evidence_appendix(self, data: dict[str, Any]) -> dict[str, Any]:
        """Build evidence appendix data from audit results.

        Args:
            data: Report data containing rules and audit information

        Returns:
            Dict with evidence data organized by category
        """
        rules = data.get("rules", [])

        # Organize evidence by rule type
        evidence: dict[str, Any] = {
            "pacing_data": [],
            "creative_data": [],
            "performance_data": [],
            "benchmark_data": [],
            "tracking_data": [],
        }

        for rule in rules:
            rule_name = rule.get("rule", "")
            findings = rule.get("findings", {})
            window = rule.get("window", "")

            if rule_name == "pacing_vs_target":
                evidence["pacing_data"].append(
                    {
                        "window": window,
                        "actual": findings.get("actual", 0.0),
                        "target": findings.get("target", 0.0),
                        "ratio": findings.get("ratio"),
                        "within_band": findings.get("within_band", False),
                    }
                )
            elif rule_name == "creative_diversity":
                evidence["creative_data"].append(
                    {
                        "window": window,
                        "video_share": findings.get("video_share", 0.0),
                        "image_share": findings.get("image_share", 0.0),
                        "shortfall": findings.get("shortfall", 0.0),
                    }
                )
            elif rule_name in ["ctr_threshold", "frequency_threshold"]:
                evidence["performance_data"].append(
                    {
                        "window": window,
                        "metric": rule_name.replace("_threshold", "").upper(),
                        "value": findings.get(
                            "ctr", findings.get("frequency", 0.0)
                        ),
                        "threshold": findings.get(
                            "min_ctr", findings.get("max_frequency", 0.0)
                        ),
                    }
                )
            elif rule_name == "performance_vs_benchmarks":
                comparisons = findings.get("comparisons", [])
                for comp in comparisons:
                    evidence["benchmark_data"].append(
                        {
                            "window": window,
                            "metric": comp.get("metric", ""),
                            "actual": comp.get("actual", 0.0),
                            "benchmark_p50": comp.get("benchmark_p50", 0.0),
                            "tier": comp.get("tier", ""),
                        }
                    )
            elif rule_name == "tracking_health":
                evidence["tracking_data"].append(
                    {
                        "window": window,
                        "conversions_present": findings.get(
                            "conversions_present", False
                        ),
                        "conv_rate": findings.get("conv_rate"),
                        "clicks": findings.get("clicks", 0),
                    }
                )

        return evidence


def render_markdown(templates_dir: Path, data: dict) -> str:
    """Legacy function for backward compatibility."""
    renderer = ReportRenderer(templates_dir)
    return renderer.render_markdown(data)


def write_text(path: str, content: str) -> None:
    """Write text content to file."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
