import numpy as np
import pytest

from backend.app.schemas.result import EngineResult
from engine.fixtures import FIXTURES, list_fixtures
from engine.interface import EngineRequest, _statistics, run_analysis

THRESHOLDS = {"alpha": 0.01, "min_effect_size": 0.2, "ci_level": 0.99}


def request(**overrides):
    values = {
        "implementation": "vulnerable",
        "fixture_id": "prefix_4",
        "sample_size": 60,
        "warmup_runs": 2,
        "seed": 19,
        "thresholds": THRESHOLDS,
    }
    return EngineRequest(**{**values, **overrides})


def test_fixtures_are_fixed_width_and_prefix_controlled():
    assert set(list_fixtures()) == set(FIXTURES)
    assert all(len(fixture.candidate) == 32 for fixture in FIXTURES.values())
    assert FIXTURES["no_match"].candidate[0] != bytes(range(32))[0]
    assert FIXTURES["prefix_1"].candidate[:1] == bytes(range(32))[:1]
    assert FIXTURES["prefix_1"].candidate[1] != bytes(range(32))[1]
    assert FIXTURES["prefix_4"].candidate[:4] == bytes(range(32))[:4]
    assert FIXTURES["prefix_4"].candidate[4] != bytes(range(32))[4]
    assert FIXTURES["full_match"].candidate == bytes(range(32))


def test_analysis_returns_schema_valid_chart_ready_measurements():
    result = run_analysis(request())

    EngineResult.model_validate(result)
    evidence = result["evidence"]
    assert evidence["sample_size_per_group"] == 60
    assert evidence["comparison"] == "prefix_4 versus no_match"
    assert len(evidence["histogram"]["bin_edges_ns"]) == 21
    assert sum(evidence["histogram"]["baseline_counts"]) == 60
    assert sum(evidence["histogram"]["fixture_counts"]) == 60
    assert evidence["jitter"]["injected"] is False


def test_seed_reproduces_measurement_schedule_and_jitter():
    first = run_analysis(request(fixture_id="prefix_4_jitter"))
    second = run_analysis(request(fixture_id="prefix_4_jitter"))

    assert first["evidence"]["schedule_sha256"] == second["evidence"]["schedule_sha256"]
    assert first["evidence"]["jitter"]["injected"] is True
    assert first["evidence"]["jitter"]["sequence_sha256"] == second["evidence"]["jitter"][
        "sequence_sha256"
    ]


def test_constant_time_mode_runs_through_same_contract():
    result = run_analysis(request(implementation="constant_time"))

    EngineResult.model_validate(result)
    assert result["evidence"]["implementation"] == "constant_time"


@pytest.mark.parametrize(
    "overrides",
    [
        {"implementation": "unknown"},
        {"fixture_id": "not_whitelisted"},
        {"sample_size": 29},
        {"sample_size": True},
        {"warmup_runs": 501},
        {"seed": -1},
        {"thresholds": {**THRESHOLDS, "alpha": float("nan")}},
    ],
)
def test_invalid_engine_requests_are_rejected(overrides):
    with pytest.raises(ValueError):
        run_analysis(request(**overrides))


def test_statistical_decision_uses_significance_effect_and_interval():
    baseline = np.arange(60, dtype=float)
    leak = baseline + 100
    no_leak = baseline.copy()
    noisy_difference = np.tile([-1.0, 1.0], 30) + 0.23

    leak_stats = _statistics(baseline, leak, THRESHOLDS)
    no_leak_stats = _statistics(baseline, no_leak, THRESHOLDS)
    mixed_thresholds = {"alpha": 0.1, "min_effect_size": 0.5, "ci_level": 0.999}
    mixed_stats = _statistics(
        baseline, baseline + noisy_difference, mixed_thresholds
    )

    assert leak_stats[6:8] == ("leak_detected", "high")
    assert no_leak_stats[6:8] == ("no_leak_detected", "info")
    assert mixed_stats[2] < mixed_thresholds["alpha"]
    assert mixed_stats[3] <= 0 <= mixed_stats[4]
    assert mixed_stats[6] == "inconclusive"
