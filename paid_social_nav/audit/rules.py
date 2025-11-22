from __future__ import annotations

from dataclasses import dataclass
from typing import Any


dataclass_kwargs = {"slots": True}


@dataclass(**dataclass_kwargs)
class RuleResult:
    rule: str
    level: str
    window: str
    score: float  # 0-100
    findings: dict[str, Any]


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _score_linear_ok_above(actual: float, min_value: float) -> float:
    if min_value <= 0:
        return 100.0 if actual >= 0 else 0.0
    if actual >= min_value:
        return 100.0
    return 100.0 * _clamp01(actual / min_value)


def _score_linear_ok_below(
    actual: float, max_value: float, overage_cap: float = 1.0
) -> float:
    if max_value <= 0:
        return 0.0
    if actual <= max_value:
        return 100.0
    denom = max_value * overage_cap
    if denom <= 0:
        return 0.0
    over = (actual - max_value) / denom
    return 100.0 * _clamp01(1.0 - over)


def pacing_vs_target(
    actual_spend: float,
    target_spend: float,
    tolerance: float = 0.1,
    tol_cap: float = 0.5,
    level: str = "account",
    window: str = "last_7d",
) -> RuleResult:
    if target_spend <= 0:
        score = 100.0 if actual_spend <= 0 else 0.0
        return RuleResult(
            rule="pacing_vs_target",
            level=level,
            window=window,
            score=score,
            findings={
                "actual": actual_spend,
                "target": target_spend,
                "ratio": None,
                "within_band": actual_spend <= 0,
            },
        )
    ratio = actual_spend / target_spend
    diff = abs(1.0 - ratio)
    if diff <= tolerance:
        score = 100.0
    else:
        excess = diff - tolerance
        denom = max(1e-9, tol_cap - tolerance)
        penalty = excess / denom
        score = 100.0 * _clamp01(1.0 - penalty)
    return RuleResult(
        rule="pacing_vs_target",
        level=level,
        window=window,
        score=score,
        findings={
            "actual": actual_spend,
            "target": target_spend,
            "ratio": ratio,
            "within_band": diff <= tolerance,
        },
    )


def ctr_threshold(
    ctr: float,
    min_ctr: float,
    level: str = "campaign",
    window: str = "last_7d",
) -> RuleResult:
    score = _score_linear_ok_above(ctr, min_ctr)
    return RuleResult(
        rule="ctr_threshold",
        level=level,
        window=window,
        score=score,
        findings={"ctr": ctr, "min_ctr": min_ctr},
    )


def frequency_threshold(
    frequency: float,
    max_frequency: float,
    overage_cap: float = 1.0,
    level: str = "campaign",
    window: str = "last_7d",
) -> RuleResult:
    score = _score_linear_ok_below(frequency, max_frequency, overage_cap=overage_cap)
    return RuleResult(
        rule="frequency_threshold",
        level=level,
        window=window,
        score=score,
        findings={"frequency": frequency, "max_frequency": max_frequency},
    )


def budget_concentration(
    top_n_cum_share: float,
    max_share: float,
    level: str = "campaign",
    window: str = "last_7d",
) -> RuleResult:
    if max_share <= 0:
        score = 0.0 if top_n_cum_share > 0 else 100.0
    elif top_n_cum_share <= max_share:
        score = 100.0
    else:
        denom = max(1e-9, 1.0 - max_share)
        over = (top_n_cum_share - max_share) / denom
        score = 100.0 * _clamp01(1.0 - over)
    return RuleResult(
        rule="budget_concentration",
        level=level,
        window=window,
        score=score,
        findings={"top_n_cum_share": top_n_cum_share, "max_share": max_share},
    )


def creative_diversity(
    video_share: float,
    image_share: float,
    min_video_share: float = 0.2,
    min_image_share: float = 0.2,
    level: str = "campaign",
    window: str = "last_28d",
) -> RuleResult:
    shortfall = max(
        max(0.0, min_video_share - (video_share or 0.0)),
        max(0.0, min_image_share - (image_share or 0.0)),
    )
    score = 100.0 * (1.0 - _clamp01(shortfall / 1.0))
    return RuleResult(
        rule="creative_diversity",
        level=level,
        window=window,
        score=score,
        findings={
            "video_share": video_share,
            "image_share": image_share,
            "min_video_share": min_video_share,
            "min_image_share": min_image_share,
            "shortfall": shortfall,
        },
    )


def tracking_health(
    conversions_present: bool,
    conv_rate: float | None,
    min_conv_rate: float = 0.01,
    min_clicks: int = 100,
    clicks: int = 0,
    level: str = "campaign",
    window: str = "last_28d",
) -> RuleResult:
    if conversions_present:
        score = 100.0
    else:
        if clicks >= min_clicks and conv_rate is not None and conv_rate > 0:
            score = _score_linear_ok_above(conv_rate, min_conv_rate)
        else:
            score = 0.0
    return RuleResult(
        rule="tracking_health",
        level=level,
        window=window,
        score=score,
        findings={
            "conversions_present": conversions_present,
            "conv_rate": conv_rate,
            "min_conv_rate": min_conv_rate,
            "clicks": clicks,
            "min_clicks": min_clicks,
        },
    )


def performance_vs_benchmarks(
    actual_metrics: dict[str, float],
    benchmarks: dict[str, dict[str, float]],
    level: str = "campaign",
    window: str = "last_28d",
) -> RuleResult:
    """Compare actual performance metrics against industry benchmarks.

    Evaluates campaign performance by comparing actual metrics (CTR, frequency, etc.)
    against industry percentile benchmarks. Returns a score based on the percentage
    of metrics that meet or exceed the 50th percentile (median) benchmark.

    Metric Skipping Behavior:
        - Metrics are skipped if not present in benchmarks dict
        - Metrics are skipped if any percentile (p25, p50, p75, p90) is None
        - Skipped metrics do not count toward the score calculation
        - If all metrics are skipped, returns neutral score (50.0)

    Args:
        actual_metrics: Dict of metric_name -> actual_value
                       Example: {"ctr": 0.015, "frequency": 2.5}
        benchmarks: Dict of metric_name -> percentiles dict
                   Example: {"ctr": {"p25": 0.01, "p50": 0.015, "p75": 0.022, "p90": 0.030}}
        level: Entity level being audited (campaign, adset, ad)
        window: Time window for the metrics (last_28d, Q4, etc.)

    Returns:
        RuleResult with:
            - score: (metrics_above_p50 / total_metrics) * 100
            - findings: Dict with comparisons, tier classifications, and counts

    Note:
        Requires all four percentiles (p25, p50, p75, p90) for each metric.
        Incomplete benchmark data causes the metric to be skipped.
    """
    from ..core.logging_config import get_logger

    logger = get_logger(__name__)

    if not benchmarks or not actual_metrics:
        # No benchmarks available - neutral score
        if benchmarks is None:
            logger.warning(
                "Benchmark rule enabled but no benchmarks available. "
                "Ensure industry/region/spend_band are configured in audit config."
            )
        return RuleResult(
            rule="performance_vs_benchmarks",
            level=level,
            window=window,
            score=50.0,
            findings={
                "comparisons": [],
                "benchmarks_available": False,
                "metrics_above_p50": 0,
                "total_metrics": 0,
            },
        )

    comparisons = []
    metrics_above_p50 = 0
    total_metrics = 0
    skipped_metrics = []

    for metric_name, actual_value in actual_metrics.items():
        if metric_name not in benchmarks:
            skipped_metrics.append(f"{metric_name} (not in benchmarks)")
            continue

        bench = benchmarks[metric_name]

        # Get all percentiles - require all to be present for accurate tier assignment
        p25 = bench.get("p25")
        p50 = bench.get("p50")
        p75 = bench.get("p75")
        p90 = bench.get("p90")

        # Skip metrics with incomplete benchmark data
        if any(v is None for v in [p25, p50, p75, p90]):
            skipped_metrics.append(f"{metric_name} (incomplete percentiles)")
            continue

        total_metrics += 1

        # Determine percentile tier
        if actual_value >= p90:
            tier = "p90+"
        elif actual_value >= p75:
            tier = "p75-p90"
        elif actual_value >= p50:
            tier = "p50-p75"
        elif actual_value >= p25:
            tier = "p25-p50"
        else:
            tier = "below_p25"

        # Count p50+ as above benchmark
        if actual_value >= p50:
            metrics_above_p50 += 1

        comparisons.append({
            "metric": metric_name,
            "actual": actual_value,
            "benchmark_p50": p50,
            "benchmark_p25": p25,
            "benchmark_p75": p75,
            "benchmark_p90": p90,
            "tier": tier,
            "vs_benchmark": "above" if actual_value >= p50 else "below",
        })

    # Log if metrics were skipped
    if skipped_metrics:
        logger.info(
            f"Benchmark comparison skipped {len(skipped_metrics)} metrics: {', '.join(skipped_metrics[:3])}"
            + (f" and {len(skipped_metrics) - 3} more" if len(skipped_metrics) > 3 else "")
        )

    # Calculate overall score: weight by how many metrics beat p50
    if comparisons:
        p50_ratio = metrics_above_p50 / total_metrics if total_metrics > 0 else 0.5
        score = p50_ratio * 100.0
    else:
        logger.warning(
            "No benchmark comparisons could be made. "
            "Check that benchmarks exist for the configured metrics."
        )
        score = 50.0

    return RuleResult(
        rule="performance_vs_benchmarks",
        level=level,
        window=window,
        score=score,
        findings={
            "comparisons": comparisons,
            "benchmarks_available": True,
            "metrics_above_p50": metrics_above_p50,
            "total_metrics": total_metrics,
            "p50_ratio": metrics_above_p50 / total_metrics if total_metrics > 0 else 0.0,
        },
    )
