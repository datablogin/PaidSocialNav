from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ..storage.bq import BQClient
from . import rules


dataclass_kwargs = {"slots": True}


@dataclass(**dataclass_kwargs)
class AuditConfig:
    project: str
    dataset: str
    tenant: str
    windows: list[str]
    level: str  # 'account' | 'campaign' | 'adset' | 'ad'
    weights: dict[str, float]
    thresholds: dict[str, Any]
    top_n: int | None = None
    industry: str | None = None
    region: str | None = None
    spend_band: str | None = None


@dataclass(**dataclass_kwargs)
class AuditResult:
    overall_score: float
    rules: list[dict[str, Any]]


def run_audit(config_path: str) -> AuditResult:
    cfg = _load_config(config_path)
    engine = AuditEngine(cfg)
    result_dict = engine.run()
    return AuditResult(
        overall_score=result_dict["overall_score"], rules=result_dict["rules"]
    )


class AuditEngine:
    def __init__(self, cfg: AuditConfig, bq: BQClient | None = None):
        self.cfg = cfg
        self.bq = bq or BQClient(project=cfg.project)
        # Validate dataset identifier to reduce risk of SQL injection via table refs
        proj = cfg.project.strip()
        dset = self.cfg.dataset.strip()
        import re

        if not re.match(r"^[A-Za-z0-9_\-]+$", proj) or not re.match(
            r"^[A-Za-z0-9_]+$", dset
        ):
            raise ValueError("Invalid project/dataset identifier")
        self.dataset = f"{proj}.{dset}"

    def run(self) -> dict[str, Any]:
        per_rule: list[dict[str, Any]] = []
        weighted_sum = 0.0
        weight_total = 0.0

        kpis = self._fetch_kpis()

        # 1) Pacing vs target
        if "pacing_vs_target" in self.cfg.weights:
            w = float(self.cfg.weights.get("pacing_vs_target", 0.0))
            if w > 0:
                for window in self.cfg.windows:
                    actual = self._actual_spend(window)
                    target = self._target_spend(window)
                    rr = rules.pacing_vs_target(
                        actual_spend=actual,
                        target_spend=target,
                        tolerance=float(
                            self.cfg.thresholds.get("pacing_tolerance", 0.1)
                        ),
                        tol_cap=float(self.cfg.thresholds.get("pacing_tol_cap", 0.5)),
                        level=self.cfg.level,
                        window=window,
                    )
                per_rule.append(self._serialize_rr(rr))
                w = float(self.cfg.weights.get("pacing_vs_target", 0.0))
                weighted_sum += w * rr.score
                weight_total += w

        # 2) CTR and frequency
        if (
            "ctr_threshold" in self.cfg.weights
            or "frequency_threshold" in self.cfg.weights
        ):
            for window in self.cfg.windows:
                ctr_vals = [
                    x["ctr"]
                    for x in kpis
                    if x["window"] == window and x.get("impressions", 0) > 0
                ]
                freq_vals = [
                    x.get("frequency", 0.0) for x in kpis if x["window"] == window
                ]
                avg_ctr = sum(ctr_vals) / len(ctr_vals) if ctr_vals else 0.0
                avg_freq = sum(freq_vals) / len(freq_vals) if freq_vals else 0.0

                if "ctr_threshold" in self.cfg.weights:
                    rr = rules.ctr_threshold(
                        ctr=avg_ctr,
                        min_ctr=float(self.cfg.thresholds.get("min_ctr", 0.01)),
                        level=self.cfg.level,
                        window=window,
                    )
                    per_rule.append(self._serialize_rr(rr))
                    w = float(self.cfg.weights.get("ctr_threshold", 0.0))
                    weighted_sum += w * rr.score
                    weight_total += w

                if "frequency_threshold" in self.cfg.weights:
                    rr = rules.frequency_threshold(
                        frequency=avg_freq,
                        max_frequency=float(
                            self.cfg.thresholds.get("max_frequency", 2.5)
                        ),
                        overage_cap=float(
                            self.cfg.thresholds.get("freq_overage_cap", 1.0)
                        ),
                        level=self.cfg.level,
                        window=window,
                    )
                    per_rule.append(self._serialize_rr(rr))
                    w = float(self.cfg.weights.get("frequency_threshold", 0.0))
                    weighted_sum += w * rr.score
                    weight_total += w

        # 3) Budget concentration (top-N share)
        if "budget_concentration" in self.cfg.weights and self.cfg.top_n:
            for window in self.cfg.windows:
                top_n_share = self._fetch_top_n_share(
                    window=window, top_n=self.cfg.top_n
                )
                rr = rules.budget_concentration(
                    top_n_cum_share=top_n_share,
                    max_share=float(self.cfg.thresholds.get("max_topn_share", 0.7)),
                    level=self.cfg.level,
                    window=window,
                )
                per_rule.append(self._serialize_rr(rr))
                w = float(self.cfg.weights.get("budget_concentration", 0.0))
                weighted_sum += w * rr.score
                weight_total += w

        # 4) Creative diversity
        if "creative_diversity" in self.cfg.weights:
            for window in self.cfg.windows:
                video_share, image_share = self._fetch_creative_shares(window=window)
                rr = rules.creative_diversity(
                    video_share=video_share,
                    image_share=image_share,
                    min_video_share=float(
                        self.cfg.thresholds.get("min_video_share", 0.2)
                    ),
                    min_image_share=float(
                        self.cfg.thresholds.get("min_image_share", 0.2)
                    ),
                    level=self.cfg.level,
                    window=window,
                )
                per_rule.append(self._serialize_rr(rr))
                w = float(self.cfg.weights.get("creative_diversity", 0.0))
                weighted_sum += w * rr.score
                weight_total += w

        # 5) Tracking health
        if "tracking_health" in self.cfg.weights:
            for window in self.cfg.windows:
                clicks, conversions, conv_rate = self._fetch_tracking(window=window)
                rr = rules.tracking_health(
                    conversions_present=conversions > 0,
                    conv_rate=conv_rate,
                    min_conv_rate=float(self.cfg.thresholds.get("min_conv_rate", 0.01)),
                    min_clicks=int(
                        self.cfg.thresholds.get("min_clicks_for_tracking", 100)
                    ),
                    clicks=clicks,
                    level=self.cfg.level,
                    window=window,
                )
                per_rule.append(self._serialize_rr(rr))
                w = float(self.cfg.weights.get("tracking_health", 0.0))
                weighted_sum += w * rr.score
                weight_total += w

        # 6) Performance vs Benchmarks
        if "performance_vs_benchmarks" in self.cfg.weights:
            # Only run if benchmark mapping is configured
            if self.cfg.industry and self.cfg.region and self.cfg.spend_band:
                for window in self.cfg.windows:
                    actual_metrics = self._fetch_actual_metrics(window=window)
                    benchmarks = self._fetch_benchmarks(
                        industry=self.cfg.industry,
                        region=self.cfg.region,
                        spend_band=self.cfg.spend_band,
                    )
                    rr = rules.performance_vs_benchmarks(
                        actual_metrics=actual_metrics,
                        benchmarks=benchmarks,
                        level=self.cfg.level,
                        window=window,
                    )
                    per_rule.append(self._serialize_rr(rr))
                    w = float(self.cfg.weights.get("performance_vs_benchmarks", 0.0))
                    weighted_sum += w * rr.score
                    weight_total += w

        if weight_total <= 0:
            overall = 0.0
        else:
            overall = weighted_sum / max(weight_total, 1e-9)
        return {"overall_score": overall, "rules": per_rule}

    def _fetch_kpis(self) -> list[dict[str, Any]]:
        sql = f"""
        SELECT `window`, impressions, clicks, ctr, spend
        FROM `{self.dataset}.insights_rollups`
        WHERE level = @level
        """
        rows = self.bq.query_rows(sql, params={"level": self.cfg.level})
        for r in rows:
            for k in ("impressions", "clicks"):
                r[k] = int(r.get(k) or 0)
            for k in ("ctr", "spend"):
                r[k] = float(r.get(k) or 0.0)
        # frequency not available in current view; fill with 0
        for r in rows:
            r["frequency"] = float(r.get("frequency") or 0.0)
            r["reach"] = int(r.get("reach") or 0)
        return rows

    def _fetch_top_n_share(self, window: str, top_n: int) -> float:
        # Use the dedicated budget concentration view
        sql = f"""
        SELECT MAX(cum_share) AS top_n_share
        FROM `{self.dataset}.v_budget_concentration`
        WHERE level = @level AND `window` = @window AND rank <= @top_n
        """
        rows = self.bq.query_rows(
            sql, params={"level": self.cfg.level, "window": window, "top_n": top_n}
        )
        if not rows:
            return 0.0
        return float(rows[0].get("top_n_share") or 0.0)

    def _fetch_creative_shares(self, window: str) -> tuple[float, float]:
        # Use the creative mix view; values may be NULL until creative metrics are present
        sql = f"""
        SELECT video_share, image_share
        FROM `{self.dataset}.v_creative_mix`
        WHERE level = @level AND `window` = @window
        """
        rows = self.bq.query_rows(
            sql, params={"level": self.cfg.level, "window": window}
        )
        if not rows:
            return 0.0, 0.0
        vs = rows[0].get("video_share")
        is_ = rows[0].get("image_share")
        return float(vs or 0.0), float(is_ or 0.0)

    def _fetch_tracking(self, window: str) -> tuple[int, int, float | None]:
        sql = f"""
        SELECT
          SUM(clicks) AS clicks,
          SUM(conversions) AS conversions,
          SAFE_DIVIDE(SUM(conversions), NULLIF(SUM(clicks), 0)) AS conv_rate
        FROM `{self.dataset}.insights_rollups`
        WHERE level = @level AND `window` = @window
        """
        rows = self.bq.query_rows(
            sql, params={"level": self.cfg.level, "window": window}
        )
        if not rows:
            return 0, 0, None
        clicks = int(rows[0].get("clicks") or 0)
        conv = int(rows[0].get("conversions") or 0)
        conv_rate = (
            float(rows[0].get("conv_rate"))
            if rows[0].get("conv_rate") is not None
            else None
        )
        return clicks, conv, conv_rate

    def _target_spend(self, window: str) -> float:
        plan_table = self.cfg.thresholds.get("plan_table")
        if plan_table:
            sql = f"""
            SELECT SUM(target_spend) AS target
            FROM `{plan_table}`
            WHERE window = @window
            """
            rows = self.bq.query_rows(sql, params={"window": window})
            if rows:
                return float(rows[0].get("target") or 0.0)
        per_window_targets: dict[str, float] = self.cfg.thresholds.get(
            "target_spend_by_window", {}
        )
        return float(per_window_targets.get(window, 0.0))

    def _actual_spend(self, window: str) -> float:
        # Fetch actual spend by window from v_budget_pacing
        sql = f"""
        SELECT spend
        FROM `{self.dataset}.v_budget_pacing`
        WHERE level = @level AND `window` = @window
        """
        rows = self.bq.query_rows(
            sql, params={"level": self.cfg.level, "window": window}
        )
        if not rows:
            return 0.0
        return float(rows[0].get("spend") or 0.0)

    def _fetch_actual_metrics(self, window: str) -> dict[str, float]:
        """Fetch actual performance metrics for benchmark comparison."""
        sql = f"""
        SELECT
          AVG(ctr) AS ctr,
          AVG(frequency) AS frequency,
          SAFE_DIVIDE(SUM(conversions), NULLIF(SUM(clicks), 0)) AS conv_rate,
          SAFE_DIVIDE(SUM(spend), NULLIF(SUM(clicks), 0)) AS cpc,
          SAFE_DIVIDE(SUM(spend) * 1000, NULLIF(SUM(impressions), 0)) AS cpm
        FROM `{self.dataset}.insights_rollups`
        WHERE level = @level AND `window` = @window
        """
        rows = self.bq.query_rows(
            sql, params={"level": self.cfg.level, "window": window}
        )
        if not rows:
            return {}

        row = rows[0]
        metrics = {}
        for key in ("ctr", "frequency", "conv_rate", "cpc", "cpm"):
            val = row.get(key)
            if val is not None:
                metrics[key] = float(val)
        return metrics

    def _fetch_benchmarks(
        self, industry: str, region: str, spend_band: str
    ) -> dict[str, dict[str, float]]:
        """Fetch benchmark percentiles for the given industry/region/spend_band."""
        sql = f"""
        SELECT metric_name, p25, p50, p75, p90
        FROM `{self.dataset}.benchmarks_performance`
        WHERE industry = @industry
          AND region = @region
          AND spend_band = @spend_band
        """
        rows = self.bq.query_rows(
            sql,
            params={
                "industry": industry,
                "region": region,
                "spend_band": spend_band,
            },
        )

        benchmarks = {}
        for row in rows:
            metric_name = row.get("metric_name")
            if not metric_name:
                continue
            benchmarks[metric_name] = {
                "p25": float(row["p25"]) if row.get("p25") is not None else None,
                "p50": float(row["p50"]) if row.get("p50") is not None else None,
                "p75": float(row["p75"]) if row.get("p75") is not None else None,
                "p90": float(row["p90"]) if row.get("p90") is not None else None,
            }
        return benchmarks

    @staticmethod
    def _serialize_rr(rr: rules.RuleResult) -> dict[str, Any]:
        return {
            "rule": rr.rule,
            "level": rr.level,
            "window": rr.window,
            "score": rr.score,
            "findings": rr.findings,
        }


def _load_config(path: str) -> AuditConfig:
    data = yaml.safe_load(Path(path).read_text())
    return AuditConfig(
        project=data["project"],
        dataset=data["dataset"],
        tenant=data.get("tenant", ""),
        windows=list(data.get("windows", [])),
        level=str(data.get("level", "campaign")),
        weights=dict(data.get("weights", {})),
        thresholds=dict(data.get("thresholds", {})),
        top_n=data.get("top_n"),
        industry=data.get("industry"),
        region=data.get("region"),
        spend_band=data.get("spend_band"),
    )
