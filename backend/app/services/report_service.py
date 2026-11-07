import hashlib
import json
from datetime import timezone

from sqlalchemy.orm import Session

from backend.app.core.redact import redact
from backend.app.models import Submission
from backend.app.models.tables import utcnow
from backend.app.repositories import audit_repo

REPORT_VERSION = "1"
LINKED_ACTIONS = ("submission.create", "submission.run")


def _iso(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def build_report(db: Session, sub: Submission) -> dict:
    res = sub.result
    events = audit_repo.list_for_resource(db, "submission", sub.id, LINKED_ACTIONS)
    body = {
        "report_version": REPORT_VERSION,
        "generated_at": _iso(utcnow()),
        "submission": {
            "id": sub.id, "label": sub.label, "implementation": sub.implementation,
            "fixture_id": sub.fixture_id, "sample_size": sub.sample_size,
            "warmup_runs": sub.warmup_runs, "seed": sub.seed, "status": sub.status,
            "created_at": _iso(sub.created_at), "completed_at": _iso(sub.completed_at),
        },
        "result": {
            "decision": res.decision, "severity": res.severity, "confidence": res.confidence,
            "p_value": res.p_value, "effect_size": res.effect_size,
            "ci_low": res.ci_low, "ci_high": res.ci_high,
            "evidence": redact(res.evidence), "reasons": list(res.reasons),
            "rule_name": res.rule_name, "rule_version": res.rule_version,
            "engine_version": res.engine_version, "thresholds": res.thresholds,
        },
        "evidence_links": {
            "result_id": res.id,
            "audit_events": [
                {"id": e.id, "action": e.action, "outcome": e.outcome, "timestamp": _iso(e.timestamp)}
                for e in events
            ],
        },
        "reproduction": {
            "reproducible_with_seed": sub.seed is not None,
            "how": "Re-run with the same implementation, fixture, sample size, warm-up runs, "
                   "seed and thresholds listed in this report.",
        },
    }
    body["integrity"] = {
        "algorithm": "SHA-256",
        "covers": "every field except integrity",
        "report_digest": hashlib.sha256(canonical(body)).hexdigest(),
    }
    return body