"""Run the proposal's T1-T6 engine demonstrations and print a JSON evidence report."""

import json
import math

from engine.fixtures import FIXTURES
from engine.interface import ENGINE_VERSION, EngineRequest, run_analysis

THRESHOLDS = {"alpha": 0.01, "min_effect_size": 0.2, "ci_level": 0.99}


def _request(
    fixture_id: str,
    sample_size: int,
    *,
    implementation: str = "vulnerable",
    seed: int = 2026,
) -> EngineRequest:
    return EngineRequest(
        implementation=implementation,
        fixture_id=fixture_id,
        sample_size=sample_size,
        warmup_runs=20,
        seed=seed,
        thresholds=dict(THRESHOLDS),
    )


def _case(
    test_id: str,
    title: str,
    inputs: dict,
    expected: str,
    actual: dict,
    evidence: dict,
    passed: bool,
) -> dict:
    return {
        "id": test_id,
        "title": title,
        "inputs": inputs,
        "expected": expected,
        "actual": actual,
        "evidence": evidence,
        "passed": passed,
    }


def _summarize_result(result: dict) -> dict:
    evidence = result["evidence"]
    return {
        "decision": result["decision"],
        "severity": result["severity"],
        "confidence": result["confidence"],
        "p_value": result["p_value"],
        "effect_size": result["effect_size"],
        "ci_ns": [result["ci_low"], result["ci_high"]],
        "mean_difference_ns": evidence["mean_difference_ns"],
    }


def _ci_width(result: dict) -> float:
    return result["ci_high"] - result["ci_low"]


def run_evaluation() -> dict:
    cases = []

    small_size, large_size = 30, 300
    small = run_analysis(_request("prefix_1", small_size))
    large = run_analysis(_request("prefix_1", large_size))
    small_counts = small["evidence"]["histogram"]
    large_counts = large["evidence"]["histogram"]
    t1_passed = (
        small["evidence"]["sample_size_per_group"] == small_size
        and large["evidence"]["sample_size_per_group"] == large_size
        and sum(small_counts["baseline_counts"]) == small_size
        and sum(small_counts["fixture_counts"]) == small_size
        and sum(large_counts["baseline_counts"]) == large_size
        and sum(large_counts["fixture_counts"]) == large_size
    )
    cases.append(
        _case(
            "T1",
            "Sample-size sensitivity",
            {"fixture_id": "prefix_1", "sample_sizes_per_group": [small_size, large_size]},
            "Both runs report their requested sample count and complete histograms.",
            {
                "sample_sizes_per_group": [
                    small["evidence"]["sample_size_per_group"],
                    large["evidence"]["sample_size_per_group"],
                ],
                "ci_widths_ns": [_ci_width(small), _ci_width(large)],
            },
            {
                "small_histogram_counts": [
                    sum(small_counts["baseline_counts"]),
                    sum(small_counts["fixture_counts"]),
                ],
                "large_histogram_counts": [
                    sum(large_counts["baseline_counts"]),
                    sum(large_counts["fixture_counts"]),
                ],
            },
            t1_passed,
        )
    )

    jitter_result = run_analysis(_request("prefix_4_jitter", 60))
    jitter = jitter_result["evidence"]["jitter"]
    t2_passed = (
        jitter["injected"]
        and jitter["stddev_ns"] == FIXTURES["prefix_4_jitter"].jitter_stddev_ns
        and isinstance(jitter["sequence_sha256"], str)
        and len(jitter["sequence_sha256"]) == 64
    )
    cases.append(
        _case(
            "T2",
            "Controlled jitter",
            {"fixture_id": "prefix_4_jitter", "sample_size_per_group": 60},
            "Fixture reports enabled 250 ns jitter and a digest for the simulated noise.",
            {
                "jitter_enabled": jitter["injected"],
                "jitter_stddev_ns": jitter["stddev_ns"],
                "sequence_sha256": jitter["sequence_sha256"],
            },
            _summarize_result(jitter_result),
            t2_passed,
        )
    )

    prefix_ids = ("no_match", "prefix_1", "prefix_4", "full_match")
    prefix_results = {
        fixture_id: run_analysis(_request(fixture_id, 60))
        for fixture_id in prefix_ids
    }
    prefix_actual = {
        fixture_id: result["evidence"]["fixture_matching_prefix_bytes"]
        for fixture_id, result in prefix_results.items()
    }
    prefix_expected = {
        fixture_id: FIXTURES[fixture_id].matching_prefix_bytes
        for fixture_id in prefix_ids
    }
    t3_passed = prefix_actual == prefix_expected
    cases.append(
        _case(
            "T3",
            "Prefix guesses",
            {"fixture_ids": list(prefix_ids), "sample_size_per_group": 60},
            "Each selected fixture has the documented fixed-width prefix length.",
            prefix_actual,
            {
                fixture_id: _summarize_result(result)
                for fixture_id, result in prefix_results.items()
            },
            t3_passed,
        )
    )

    comparison_results = {
        implementation: run_analysis(
            _request("prefix_4", 100, implementation=implementation)
        )
        for implementation in ("vulnerable", "constant_time")
    }
    comparison_actual = {
        implementation: result["evidence"]["implementation"]
        for implementation, result in comparison_results.items()
    }
    t4_passed = comparison_actual == {
        "vulnerable": "vulnerable",
        "constant_time": "constant_time",
    }
    cases.append(
        _case(
            "T4",
            "Vulnerable and constant-time comparison",
            {
                "fixture_id": "prefix_4",
                "sample_size_per_group": 100,
                "implementations": list(comparison_results),
            },
            "Both implementations run the same fixture and report their identity.",
            comparison_actual,
            {
                implementation: _summarize_result(result)
                for implementation, result in comparison_results.items()
            },
            t4_passed,
        )
    )

    interval_result = run_analysis(_request("prefix_4", 100))
    interval_level = interval_result["thresholds"]["ci_level"]
    interval_actual = {
        "confidence": interval_result["confidence"],
        "ci_level": interval_level,
        "ci_ns": [interval_result["ci_low"], interval_result["ci_high"]],
    }
    t5_passed = (
        interval_actual["confidence"] == interval_level
        and interval_result["ci_low"] <= interval_result["ci_high"]
        and all(math.isfinite(value) for value in interval_actual["ci_ns"])
    )
    cases.append(
        _case(
            "T5",
            "Confidence interval",
            {"fixture_id": "prefix_4", "sample_size_per_group": 100},
            "Confidence equals the configured CI level and finite interval bounds are ordered.",
            interval_actual,
            _summarize_result(interval_result),
            t5_passed,
        )
    )

    reproducible_request = _request("prefix_4_jitter", 60, seed=8675309)
    repeat_first = run_analysis(reproducible_request)["evidence"]
    repeat_second = run_analysis(reproducible_request)["evidence"]
    repeat_actual = {
        "schedule_sha256_matches": (
            repeat_first["schedule_sha256"] == repeat_second["schedule_sha256"]
        ),
        "jitter_sequence_sha256_matches": (
            repeat_first["jitter"]["sequence_sha256"]
            == repeat_second["jitter"]["sequence_sha256"]
        ),
    }
    t6_passed = all(repeat_actual.values())
    cases.append(
        _case(
            "T6",
            "Seed reproducibility",
            {
                "fixture_id": "prefix_4_jitter",
                "sample_size_per_group": 60,
                "seed": 8675309,
            },
            "Repeated seeded runs produce identical schedule and simulated-jitter digests.",
            repeat_actual,
            {
                "schedule_sha256": repeat_first["schedule_sha256"],
                "jitter_sequence_sha256": repeat_first["jitter"]["sequence_sha256"],
            },
            t6_passed,
        )
    )

    return {
        "engine_version": ENGINE_VERSION,
        "passed": sum(case["passed"] for case in cases),
        "total": len(cases),
        "cases": cases,
    }


def main() -> None:
    report = run_evaluation()
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["passed"] != report["total"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
