"""Reproduce the report's exploratory local timing measurements (no network targets)."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import random
import statistics
import time

from engine.interface import EngineRequest, run_analysis
from scripts.qa import environment_details


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/qa/measurements.json"))
    args = parser.parse_args()
    thresholds = {"alpha": 0.01, "min_effect_size": 0.2, "ci_level": 0.99}
    seeds = list(range(2026, 2031))
    rows = []
    started = datetime.now(timezone.utc).isoformat()
    for seed in seeds:
        combinations = [(implementation, fixture) for implementation in ("vulnerable", "constant_time")
                        for fixture in ("no_match", "prefix_1", "prefix_4", "full_match")]
        random.Random(seed).shuffle(combinations)
        for implementation, fixture in combinations:
            request = EngineRequest(implementation=implementation, fixture_id=fixture,
                                    sample_size=300, warmup_runs=20, seed=seed, thresholds=dict(thresholds))
            begin = time.perf_counter_ns()
            result = run_analysis(request)
            elapsed_ms = (time.perf_counter_ns() - begin) / 1_000_000
            rows.append({
                "implementation": implementation, "fixture_id": fixture, "seed": seed,
                "expected_group": "positive" if implementation == "vulnerable" and fixture != "no_match" else "negative",
                "engine_call_ms": elapsed_ms, "decision": result["decision"],
                "p_value": result["p_value"], "effect_size": result["effect_size"],
                "ci_ns": [result["ci_low"], result["ci_high"]],
                "mean_difference_ns": result["evidence"]["mean_difference_ns"],
                "schedule_sha256": result["evidence"]["schedule_sha256"],
            })
    metrics = {}
    for group in ("positive", "negative"):
        subset = [row for row in rows if row["expected_group"] == group]
        counts = Counter(row["decision"] for row in subset)
        metrics[group] = {"runs": len(subset), "decisions": dict(counts),
                          "inconclusive_fraction": counts["inconclusive"] / len(subset)}
    positives, negatives = metrics["positive"], metrics["negative"]
    positives["detection_fraction"] = positives["decisions"].get("leak_detected", 0) / positives["runs"]
    positives["explicit_miss_fraction"] = positives["decisions"].get("no_leak_detected", 0) / positives["runs"]
    negatives["alert_fraction"] = negatives["decisions"].get("leak_detected", 0) / negatives["runs"]
    durations = sorted(row["engine_call_ms"] for row in rows)
    report = {
        "started_at_utc": started, "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "environment": environment_details(),
        "protocol_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "settings": {"sample_size_per_group": 300, "warmup_runs": 20,
                     "seeds": seeds, "thresholds": thresholds, "run_order": "shuffled per seed"},
        "interpretation": "Exploratory one-host observations. Negative controls include hmac.compare_digest; "
                          "alerts do not establish a defect in that comparator. Inconclusive outcomes are separate "
                          "from explicit misses. Rates are not population accuracy estimates. Engine-call latency "
                          "includes warm-up, sampling and statistics, but excludes HTTP/database/UI work.",
        "metrics": metrics,
        "latency_ms": {"median": statistics.median(durations),
                       "p95_nearest_rank": durations[math.ceil(0.95 * len(durations)) - 1],
                       "min": min(durations), "max": max(durations)},
        "runs": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"metrics": metrics, "latency_ms": report["latency_ms"]}, indent=2))
    print(f"Saved {len(rows)} measured runs to {args.output}")


if __name__ == "__main__":
    main()
