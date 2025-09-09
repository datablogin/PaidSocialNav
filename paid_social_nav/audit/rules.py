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


def _score_linear_ok_below(actual: float, max_value: float, overage_cap: float = 1.0) -> float:
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
        over = (top_n_cum_share - max_share) / (1.0 - max_share)
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

