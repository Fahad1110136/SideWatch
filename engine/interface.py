"""Timing-leakage experiment engine behind the backend's stable contract."""

from dataclasses import dataclass
import hashlib
import hmac
import math
import random
from collections.abc import Mapping
from time import perf_counter_ns

import numpy as np
from scipy import stats

from engine.fixtures import (
    FIXTURES,
    REFERENCE_BYTES,
    Fixture,
    list_fixtures as _list_fixtures,
)

ENGINE_VERSION = "1.0.0"
RULE_NAME = "paired_timing_leakage"
RULE_VERSION = "1"
CONTROL_FIXTURE = "no_match"
TIMED_CALLS_PER_SAMPLE = 64
HISTOGRAM_BINS = 20

_THRESHOLD_BOUNDS = {
    "alpha": (0.0001, 0.1),
    "min_effect_size": (0.0, 5.0),
    "ci_level": (0.8, 0.999),
}


def list_fixtures() -> list[str]:
    return _list_fixtures()


@dataclass(frozen=True)
class EngineRequest:
    implementation: str
    fixture_id: str
    sample_size: int
    warmup_runs: int
    seed: int | None
    thresholds: dict


def _validate_request(req: EngineRequest) -> None:
    if not isinstance(req.implementation, str) or req.implementation not in {
        "vulnerable",
        "constant_time",
    }:
        raise ValueError("unsupported implementation")
    if not isinstance(req.fixture_id, str) or req.fixture_id not in FIXTURES:
        raise ValueError("unknown fixture")
    if type(req.sample_size) is not int or not 30 <= req.sample_size <= 5000:
        raise ValueError("sample_size must be an integer from 30 to 5000")
    if type(req.warmup_runs) is not int or not 0 <= req.warmup_runs <= 500:
        raise ValueError("warmup_runs must be an integer from 0 to 500")
    if req.seed is not None and (
        type(req.seed) is not int or not 0 <= req.seed <= 2**31 - 1
    ):
        raise ValueError("seed must be an integer from 0 to 2**31 - 1")
    if not isinstance(req.thresholds, Mapping):
        raise ValueError("thresholds must be a mapping")
    if set(req.thresholds) != set(_THRESHOLD_BOUNDS):
        raise ValueError(
            "thresholds must contain exactly alpha, min_effect_size, and ci_level"
        )
    for name, (minimum, maximum) in _THRESHOLD_BOUNDS.items():
        value = req.thresholds.get(name)
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not minimum <= value <= maximum
            or not math.isfinite(value)
        ):
            raise ValueError(f"invalid {name} threshold")


def _vulnerable_compare(candidate: bytes, reference: bytes) -> bool:
    for candidate_byte, reference_byte in zip(candidate, reference):
        if candidate_byte != reference_byte:
            return False
    return len(candidate) == len(reference)


def _constant_time_compare(candidate: bytes, reference: bytes) -> bool:
    return hmac.compare_digest(candidate, reference)


def _timed_batch(compare, candidate: bytes) -> float:
    start = perf_counter_ns()
    for _ in range(TIMED_CALLS_PER_SAMPLE):
        compare(candidate, REFERENCE_BYTES)
    return (perf_counter_ns() - start) / TIMED_CALLS_PER_SAMPLE


def _histogram(
    baseline: np.ndarray, fixture: np.ndarray
) -> dict[str, list[int] | list[float]]:
    combined = np.concatenate((baseline, fixture))
    edges = np.histogram_bin_edges(combined, bins=HISTOGRAM_BINS)
    baseline_counts, _ = np.histogram(baseline, bins=edges)
    fixture_counts, _ = np.histogram(fixture, bins=edges)
    return {
        "bin_edges_ns": [float(value) for value in edges],
        "baseline_counts": [int(value) for value in baseline_counts],
        "fixture_counts": [int(value) for value in fixture_counts],
    }


def _statistics(
    baseline: np.ndarray,
    fixture: np.ndarray,
    thresholds: Mapping[str, float],
) -> tuple[float, float, float, float, float, float, str, str]:
    differences = fixture - baseline
    mean_difference = float(np.mean(differences))
    std_difference = float(np.std(differences, ddof=1))
    if std_difference == 0:
        effect_size = (
            0.0 if mean_difference == 0 else math.copysign(1000.0, mean_difference)
        )
        p_value = 1.0 if mean_difference == 0 else 0.0
    else:
        effect_size = mean_difference / std_difference
        test = stats.ttest_rel(fixture, baseline)
        p_value = float(test.pvalue) if math.isfinite(float(test.pvalue)) else 1.0

    confidence_level = float(thresholds["ci_level"])
    standard_error = std_difference / math.sqrt(len(differences))
    critical_value = float(stats.t.ppf((1 + confidence_level) / 2, len(differences) - 1))
    ci_low = mean_difference - critical_value * standard_error
    ci_high = mean_difference + critical_value * standard_error

    significant_difference = p_value < float(thresholds["alpha"]) and (
        ci_low > 0 or ci_high < 0
    )
    if significant_difference and abs(effect_size) >= float(thresholds["min_effect_size"]):
        decision = "leak_detected"
        severity = (
            "high"
            if abs(effect_size) >= 0.8
            else "medium"
            if abs(effect_size) >= 0.5
            else "low"
        )
    elif (
        p_value >= float(thresholds["alpha"])
        and ci_low <= 0 <= ci_high
        and abs(effect_size) <= float(thresholds["min_effect_size"])
    ):
        decision = "no_leak_detected"
        severity = "info"
    else:
        decision = "inconclusive"
        severity = "low"

    return (
        mean_difference,
        effect_size,
        p_value,
        ci_low,
        ci_high,
        1 - p_value,
        decision,
        severity,
    )


def run_analysis(req: EngineRequest) -> dict:
    """Measure a fixture against the no-match control and return explainable statistics."""
    _validate_request(req)
    fixture: Fixture = FIXTURES[req.fixture_id]
    compare = (
        _vulnerable_compare
        if req.implementation == "vulnerable"
        else _constant_time_compare
    )
    baseline_candidate = FIXTURES[CONTROL_FIXTURE].candidate
    rng = random.Random(req.seed)

    for _ in range(req.warmup_runs):
        compare(baseline_candidate, REFERENCE_BYTES)
        compare(fixture.candidate, REFERENCE_BYTES)

    target_first = [bool(rng.getrandbits(1)) for _ in range(req.sample_size)]
    schedule_hash = hashlib.sha256(
        bytes(target_first)
    ).hexdigest()
    baseline_jitter = np.zeros(req.sample_size, dtype=np.float64)
    fixture_jitter = np.zeros(req.sample_size, dtype=np.float64)
    jitter_hash = None
    if fixture.jitter_stddev_ns:
        baseline_jitter = np.array(
            [rng.gauss(0, fixture.jitter_stddev_ns) for _ in range(req.sample_size)]
        )
        fixture_jitter = np.array(
            [rng.gauss(0, fixture.jitter_stddev_ns) for _ in range(req.sample_size)]
        )
        jitter_hash = hashlib.sha256(
            baseline_jitter.tobytes() + fixture_jitter.tobytes()
        ).hexdigest()

    baseline_samples = np.empty(req.sample_size, dtype=np.float64)
    fixture_samples = np.empty(req.sample_size, dtype=np.float64)
    clamped_jitter_samples = 0

    for index, measure_fixture_first in enumerate(target_first):
        if measure_fixture_first:
            fixture_time = _timed_batch(compare, fixture.candidate)
            baseline_time = _timed_batch(compare, baseline_candidate)
        else:
            baseline_time = _timed_batch(compare, baseline_candidate)
            fixture_time = _timed_batch(compare, fixture.candidate)

        if fixture.jitter_stddev_ns:
            baseline_time += baseline_jitter[index]
            fixture_time += fixture_jitter[index]
            if baseline_time < 0:
                baseline_time = 0.0
                clamped_jitter_samples += 1
            if fixture_time < 0:
                fixture_time = 0.0
                clamped_jitter_samples += 1
        baseline_samples[index] = baseline_time
        fixture_samples[index] = fixture_time

    (
        mean_difference,
        effect_size,
        p_value,
        ci_low,
        ci_high,
        confidence,
        decision,
        severity,
    ) = _statistics(baseline_samples, fixture_samples, req.thresholds)

    if decision == "leak_detected":
        reasons = [
            f"The fixture was {mean_difference:.2f} ns "
            f"{'slower' if mean_difference >= 0 else 'faster'} than the no-match control "
            f"(paired p={p_value:.4g}, Cohen's dz={effect_size:.3f}).",
            "Use a fixed-length constant-time comparison such as hmac.compare_digest; "
            "do not reveal comparison progress through responses.",
        ]
    elif decision == "no_leak_detected":
        reasons = [
            "No statistically significant timing difference above the configured effect-size "
            "threshold was detected; this does not prove the implementation is constant-time.",
            "Continue to use a fixed-length constant-time comparison rather than relying on "
            "this measurement as proof.",
        ]
    else:
        reasons = [
            "The measurements are inconclusive under the configured thresholds; collect more "
            "samples or reduce measurement jitter before drawing a conclusion.",
            "Use a constant-time comparison while the timing result remains unresolved.",
        ]

    return {
        "decision": decision,
        "severity": severity,
        "confidence": min(1.0, max(0.0, confidence)),
        "p_value": min(1.0, max(0.0, p_value)),
        "effect_size": float(effect_size),
        "ci_low": float(ci_low),
        "ci_high": float(ci_high),
        "evidence": {
            "method": "paired_wall_clock_microbenchmark",
            "comparison": f"{req.fixture_id} versus {CONTROL_FIXTURE}",
            "implementation": req.implementation,
            "fixture_description": fixture.description,
            "sample_size_per_group": req.sample_size,
            "warmup_runs_per_group": req.warmup_runs,
            "timed_calls_per_sample": TIMED_CALLS_PER_SAMPLE,
            "mean_difference_ns": mean_difference,
            "fixture_matching_prefix_bytes": fixture.matching_prefix_bytes,
            "jitter": {
                "injected": fixture.jitter_stddev_ns > 0,
                "model": "independent Gaussian overlay on each measured sample",
                "stddev_ns": fixture.jitter_stddev_ns,
                "clamped_samples": clamped_jitter_samples,
                "sequence_sha256": jitter_hash,
            },
            "seed": req.seed,
            "schedule_sha256": schedule_hash,
            "confidence_interpretation": (
                "1 - two-sided paired-test p-value; not a posterior probability"
            ),
            "histogram": _histogram(baseline_samples, fixture_samples),
            "baseline_summary_ns": {
                "mean": float(np.mean(baseline_samples)),
                "median": float(np.median(baseline_samples)),
                "stddev": float(np.std(baseline_samples, ddof=1)),
            },
            "fixture_summary_ns": {
                "mean": float(np.mean(fixture_samples)),
                "median": float(np.median(fixture_samples)),
                "stddev": float(np.std(fixture_samples, ddof=1)),
            },
            "paired_difference_summary_ns": {
                "mean": mean_difference,
                "stddev": float(np.std(fixture_samples - baseline_samples, ddof=1)),
            },
        },
        "reasons": reasons,
        "rule_name": RULE_NAME,
        "rule_version": RULE_VERSION,
        "engine_version": ENGINE_VERSION,
        "thresholds": dict(req.thresholds),
    }