"""Contract between the backend (Member A) and the security engine (Member B).

PLACEHOLDER: Member B replaces run_analysis() and FIXTURES with the real engine.
Keep the function signatures and the returned dict keys unchanged.
"""
from dataclasses import dataclass

ENGINE_VERSION = "0.0.1-stub"
FIXTURES = ["no_match", "prefix_1", "prefix_4", "full_match"]  # server-side whitelist


@dataclass(frozen=True)
class EngineRequest:
    implementation: str          # "vulnerable" | "constant_time"
    fixture_id: str              # always one of list_fixtures()
    sample_size: int
    warmup_runs: int
    seed: int | None
    thresholds: dict             # e.g. {"alpha": 0.01, "min_effect_size": 0.2, "ci_level": 0.99}


def list_fixtures() -> list[str]:
    return list(FIXTURES)


def run_analysis(req: EngineRequest) -> dict:
    """Must return a dict that validates against backend.app.schemas.result.EngineResult."""
    leaky = req.implementation == "vulnerable"
    return {
        "decision": "leak_detected" if leaky else "no_leak_detected",
        "severity": "high" if leaky else "info",
        "confidence": 0.99 if leaky else 0.95,
        "p_value": 0.0001 if leaky else 0.62,
        "effect_size": 1.8 if leaky else 0.03,
        "ci_low": 120.0 if leaky else -4.0,
        "ci_high": 180.0 if leaky else 6.0,
        "evidence": {"sample_size": req.sample_size, "placeholder": True},
        "reasons": [
            "Placeholder result from the stub engine.",
            "Early-exit comparison is expected to leak." if leaky
            else "Constant-time comparison is expected not to leak.",
        ],
        "rule_name": "stub_rule",
        "rule_version": "0",
        "engine_version": ENGINE_VERSION,
        "thresholds": {"alpha": req.thresholds["alpha"]},
    }