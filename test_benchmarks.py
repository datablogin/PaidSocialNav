#!/usr/bin/env python3
"""Test script for benchmarks feature (Issue #16).

This script tests:
1. Loading benchmark CSV data into BigQuery
2. Running audit with benchmark comparisons
3. Verifying benchmark results in audit output

Usage:
    python test_benchmarks.py
"""

from pathlib import Path

from paid_social_nav.audit.engine import run_audit
from paid_social_nav.storage.bq import load_benchmarks_csv


def test_load_benchmarks():
    """Test loading benchmarks from CSV into BigQuery."""
    print("=" * 80)
    print("TEST 1: Loading Benchmarks CSV")
    print("=" * 80)

    project_id = "puttery-golf-001"
    dataset = "paid_social"
    csv_path = str(Path(__file__).parent / "data" / "benchmarks_performance.csv")

    print(f"\nLoading benchmarks from: {csv_path}")
    print(f"Target: {project_id}.{dataset}.benchmarks_performance\n")

    try:
        rows_loaded = load_benchmarks_csv(
            project_id=project_id, dataset=dataset, csv_path=csv_path
        )
        print(f"✓ Successfully loaded {rows_loaded} benchmark rows")
        return True
    except Exception as e:
        print(f"✗ Failed to load benchmarks: {e}")
        return False


def test_audit_with_benchmarks():
    """Test running audit with benchmark comparisons."""
    print("\n" + "=" * 80)
    print("TEST 2: Running Audit with Benchmarks")
    print("=" * 80)

    config_path = str(Path(__file__).parent / "configs" / "audit_puttery.yaml")

    print(f"\nRunning audit with config: {config_path}\n")

    try:
        result = run_audit(config_path)
        print("✓ Audit completed successfully")
        print(f"  Overall Score: {result.overall_score:.2f}")
        print(f"  Total Rules: {len(result.rules)}\n")

        # Find benchmark rule results
        benchmark_rules = [
            r for r in result.rules if r["rule"] == "performance_vs_benchmarks"
        ]

        if benchmark_rules:
            print(f"✓ Found {len(benchmark_rules)} benchmark comparison(s)\n")

            for idx, rule in enumerate(benchmark_rules, 1):
                print(f"  Benchmark Result #{idx}:")
                print(f"    Window: {rule['window']}")
                print(f"    Score: {rule['score']:.2f}")
                findings = rule.get("findings", {})

                if findings.get("benchmarks_available"):
                    print(f"    Metrics Above P50: {findings['metrics_above_p50']}/{findings['total_metrics']}")
                    print(f"    P50 Ratio: {findings.get('p50_ratio', 0):.2%}")

                    comparisons = findings.get("comparisons", [])
                    if comparisons:
                        print("\n    Metric Comparisons:")
                        for comp in comparisons:
                            metric = comp["metric"]
                            actual = comp["actual"]
                            p50 = comp["benchmark_p50"]
                            tier = comp["tier"]
                            vs_bench = comp["vs_benchmark"]

                            print(f"      {metric}:")
                            print(f"        Actual: {actual:.4f}")
                            print(f"        Benchmark P50: {p50:.4f}")
                            print(f"        Tier: {tier}")
                            print(f"        vs Benchmark: {vs_bench.upper()}")
                else:
                    print("    ⚠ Benchmarks not available for this configuration")

                print()

            return True
        else:
            print("⚠ No benchmark rules found in audit results")
            print("\nAll rules executed:")
            for r in result.rules:
                print(f"  - {r['rule']} (window={r['window']}, score={r['score']:.2f})")
            return False

    except Exception as e:
        print(f"✗ Audit failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_benchmark_rule_unit():
    """Unit test for the benchmark comparison rule."""
    print("\n" + "=" * 80)
    print("TEST 3: Unit Test for Benchmark Rule")
    print("=" * 80)

    from paid_social_nav.audit import rules

    # Sample actual metrics
    actual_metrics = {
        "ctr": 0.016,  # Above p50 (0.015)
        "frequency": 2.0,  # Below p50 (2.3)
        "conv_rate": 0.018,  # Above p50 (0.015)
    }

    # Sample benchmarks (matching retail/US/10k-50k from CSV)
    benchmarks = {
        "ctr": {"p25": 0.010, "p50": 0.015, "p75": 0.022, "p90": 0.030},
        "frequency": {"p25": 1.8, "p50": 2.3, "p75": 3.0, "p90": 3.8},
        "conv_rate": {"p25": 0.010, "p50": 0.015, "p75": 0.022, "p90": 0.032},
    }

    print("\nActual Metrics:")
    for metric, value in actual_metrics.items():
        print(f"  {metric}: {value}")

    print("\nBenchmarks (retail/US/10k-50k):")
    for metric, percs in benchmarks.items():
        print(f"  {metric}: p25={percs['p25']}, p50={percs['p50']}, p75={percs['p75']}, p90={percs['p90']}")

    try:
        result = rules.performance_vs_benchmarks(
            actual_metrics=actual_metrics,
            benchmarks=benchmarks,
            level="campaign",
            window="test_window",
        )

        print("\n✓ Rule executed successfully")
        print(f"  Score: {result.score:.2f}")
        print(f"  Metrics Above P50: {result.findings['metrics_above_p50']}/{result.findings['total_metrics']}")
        print(f"  P50 Ratio: {result.findings['p50_ratio']:.2%}")

        print("\n  Comparisons:")
        for comp in result.findings["comparisons"]:
            print(f"    {comp['metric']}: {comp['actual']:.4f} vs P50 {comp['benchmark_p50']:.4f} = {comp['vs_benchmark'].upper()}")

        # Validate expected results
        expected_above = 2  # ctr and conv_rate are above p50
        actual_above = result.findings["metrics_above_p50"]

        if actual_above == expected_above:
            print(f"\n✓ Validation passed: {actual_above} metrics above P50 (expected {expected_above})")
            return True
        else:
            print(f"\n✗ Validation failed: {actual_above} metrics above P50 (expected {expected_above})")
            return False

    except Exception as e:
        print(f"✗ Rule failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all benchmark tests."""
    print("\n" + "=" * 80)
    print("BENCHMARKS FEATURE TEST SUITE (Issue #16)")
    print("=" * 80)

    results = []

    # Test 1: Load benchmarks
    results.append(("Load Benchmarks CSV", test_load_benchmarks()))

    # Test 2: Run audit with benchmarks
    results.append(("Audit with Benchmarks", test_audit_with_benchmarks()))

    # Test 3: Unit test benchmark rule
    results.append(("Benchmark Rule Unit Test", test_benchmark_rule_unit()))

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        symbol = "✓" if result else "✗"
        print(f"  {symbol} {test_name}: {status}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit(main())
