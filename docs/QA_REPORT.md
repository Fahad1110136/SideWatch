# SideWatch final QA report

Member D: automation, security testing, packaging and QA. This report supplements
the architecture, threat model and implementation description in
[the shared project document](../document.md). It covers the local educational
system and makes no production-security certification claim.

## Verified baseline

The application revision tested was `d651d53509b0cc1b9e5067c7804caec6a2af8de1`
(`Verify packaging`). The evidence records a dirty working tree because local
documentation and report material existed during collection. The runtime code
tested is from that revision; the final commit adds documentation and the
measurement protocol, without changing the application. Python was **3.12.10**
on **Windows 11 AMD64**. The dependency snapshot is
[`requirements.lock`](../requirements.lock). Collection timestamps are UTC;
the final QA run began at 2026-11-24 20:52:34 UTC, or **2026-11-25 01:52:34 PKT**.
See [environment and commands](evidence/qa-summary.json).

| Check | Outcome | Evidence |
|---|---|---|
| Full automated suite | 172/172 passed; 0 failed, errored or skipped | [JUnit report](evidence/pytest.xml), [summary](evidence/qa-summary.json) |
| Mandatory engine cases | T1-T6: 6/6 harness checks passed | [Evaluation record](evidence/evaluation.json) |
| Normal packaging workflow | All six smoke stages passed | [Smoke summary](evidence/smoke-summary.json) |
| Fresh dependency installation | Installed into a new venv without system site-packages; pinned versions match and `pip check` found no broken requirements | [Dependency check](evidence/dependency-check.json), [packaging procedure](../PACKAGING.md) |
| Exploratory timing study | 40 measured runs, five seeds | [Raw measurements](evidence/measurements.json), [collection protocol](evidence/collect_measurements.py) |
| Docker runtime and image build | Not executed: Docker unavailable | [Docker verification procedure](../PACKAGING.md#docker-path) |
| New interactive browser/accessibility rehearsal | Not executed by Member D | [Manual rehearsal script](DEMO.md) |

The suite pass fraction is **100%**, above the proposal's 80% minimum. The QA
gate requires every executed test and all six evaluation cases to pass. No
unresolved critical authorization, injection, secret-exposure or file-handling
defect was identified by the executed checks. This is a bounded finding from
the tests below, not proof that no such defect can exist.

## Requirements and evidence

| Requirement | Implementation and verification |
|---|---|
| FR-1: test harness | Input schemas, fixture whitelist and submission service; [`test_submissions_api.py`](../backend/tests/test_submissions_api.py), [`test_schemas.py`](../backend/tests/test_schemas.py) |
| FR-2: repeated measurements | Paired timing engine and seeded schedule; [`test_engine.py`](../backend/tests/test_engine.py), T1/T6 in [evaluation](evidence/evaluation.json) |
| FR-3: statistical comparison | Paired t-test, Cohen's dz, CI and three-condition decision; constructed-data branch tests in [`test_engine.py`](../backend/tests/test_engine.py), T5 evidence |
| FR-4: contrasting implementations | Early-exit comparator and `hmac.compare_digest`; T4 and [40 measured runs](evidence/measurements.json) |
| FR-5: charts | Chart-ready histogram/summary data and frontend chart code; engine histogram tests, frontend asset/static tests in [`test_frontend.py`](../backend/tests/test_frontend.py); interactive visual rendering requires the demo rehearsal |
| FR-6: mitigation recommendations | Reasons retained with results and sanitized reports; schema-valid engine output and report tests in [`test_engine.py`](../backend/tests/test_engine.py) and [`test_report_api.py`](../backend/tests/test_report_api.py) |
| Server-side role and ownership checks | Role denials, scoped submission/result/export access and administrative permissions; [`test_api.py`](../backend/tests/test_api.py), [`test_submissions_api.py`](../backend/tests/test_submissions_api.py), [`test_report_api.py`](../backend/tests/test_report_api.py), [`test_rules_api.py`](../backend/tests/test_rules_api.py) |
| Credentials, sessions and CSRF | Argon2id, hashed session tokens, expiry/revocation and session-bound CSRF; [`test_security.py`](../backend/tests/test_security.py), [`test_sessions.py`](../backend/tests/test_sessions.py), [`test_accounts_api.py`](../backend/tests/test_accounts_api.py), [`test_security_qa.py`](../backend/tests/test_security_qa.py) |
| Validation, safe errors and sensitive output | Strict schemas, parameterized repositories, body-size enforcement, redaction and export digest; schema/repository tests plus [`test_errors.py`](../backend/tests/test_errors.py), [`test_redact.py`](../backend/tests/test_redact.py), report tests |
| Audit integrity and recovery | Append-only triggers, hash chain, failure logging and actual process restarts; [`test_audit.py`](../backend/tests/test_audit.py), [`test_recovery.py`](../backend/tests/test_recovery.py), [`test_security_live.py`](../backend/tests/test_security_live.py) |
| Safe local fixtures | Server whitelist and fixed 32-byte synthetic inputs; fixture/invalid-request tests in [`test_engine.py`](../backend/tests/test_engine.py) |
| Architecture and eight or more threats | Data-flow diagram/trust boundaries and backend/engine threat mappings in [Parts 1-2](../document.md) |

File links identify the executable checks. The [JUnit snapshot](evidence/pytest.xml)
records their outcomes; the [evidence index](evidence/README.md) explains provenance
and sanitization. Static checks cannot replace runtime browser validation or a
complete injection assessment.

## T-final security review

The real HTTP test
`test_live_invalid_unauthorized_repeated_and_safe_failures` verifies malformed
JSON (422), oversized input (413), anonymous submission (401), restricted-viewer
submission (403 with an audit event), distinct completed records for repeated
requests, and safe handling of an engine exception and malformed output. Failed
runs have no result or export; a later measurement still succeeds. The separate
backend test verifies submission rate limiting. See
[`test_security_live.py`](../backend/tests/test_security_live.py) and
[`test_tfinal_backend.py`](../backend/tests/test_tfinal_backend.py).

`test_live_crash_restart_recovers_once_and_preserves_state` kills an actual
Uvicorn process after the service stores a running submission and enters a
deliberately blocked test-engine call. A fresh process reopens the same temporary
SQLite database with the same secret. It marks the interrupted record
`INTERRUPTED_BY_RESTART`, preserves completed results and the changed rule version,
accepts the active session, rejects the revoked session and verifies the audit
chain. A second restart leaves exactly one recovery event. This is engine-stage
crash recovery, not a simulation of every possible interrupted write.

The deterministic fault hooks are confined to
[`backend/tests/live_server.py`](../backend/tests/live_server.py). The packaging
smoke command uses the normal application and real engine. Each test is confined
to disposable local data and dynamically selected localhost ports.

## Measurement analysis

The official [T1-T6 record](evidence/evaluation.json) preserves all six cases'
inputs, expected output, actual output, evidence and status. Case status checks
the stated harness condition. It is separate from whether timing noise allows
the classifier to detect a particular deliberately vulnerable fixture.

| Case | Observed result | Interpretation |
|---|---|---|
| T1: sample size | CI width 38.029 ns at n=30; 3.453 ns at n=300 | Larger run produced a narrower interval here; the harness checks counts and complete histograms, not a guaranteed width ratio. |
| T2: jitter | Injected SD 250 ns; four-byte gap 140.808 ns, CI [2.411, 279.206] ns; leak detected | This noisy run retained evidence of a difference; it does not establish that every noisy run will detect a leak. |
| T3: prefix guesses | At n=60, mean gaps: control -2.240 ns; 1 byte -29.948 ns; 4 bytes 88.359 ns; all 32 bytes 734.245 ns | The one-byte positive was missed, while 4/32-byte fixtures were detected. Prefix length is not guaranteed to yield a monotonic observed curve in a short noisy run. |
| T4: comparator | At n=100, vulnerable gap 92.938 ns (leak); constant-time gap -0.281 ns (no leak) | The contrast is visible in this observation. Clean results are not a proof of constant-time behavior. |
| T5: CI | 99% interval [35.849, 117.526] ns | This is the interval on the paired mean timing difference, not a posterior probability of leakage. |
| T6: reproducibility | Both schedule and injected-jitter digests matched | Seeds reproduce ordering and simulated noise; wall-clock timing and verdicts may differ. |

The additional [measurement study](evidence/measurements.json) used both
implementations and `no_match`, `prefix_1`, `prefix_4`, `full_match`, each with
five seeds (2026-2030), 300 paired samples and 20 warm-ups. Run order was shuffled
per seed. Thresholds were alpha 0.01, minimum absolute effect size 0.2 and CI
level 0.99. The [collection protocol](evidence/collect_measurements.py) fixes
those choices and records its own SHA-256 digest.

Positive demonstrations are the vulnerable comparator with nonzero matching
prefixes: **15 runs**. Negative controls are the vulnerable comparator's
`no_match` plus all four `hmac.compare_digest` fixtures: **25 runs**. These labels
describe the educational experiment, not a claim that measured alerts certify
a defect in a vetted comparator.

| Observation | Count | Fraction within its group |
|---|---|---|
| Positive detected | 13/15 | 86.7% |
| Positive returned no leak (explicit miss) | 1/15 | 6.7% |
| Positive inconclusive | 1/15 | 6.7% |
| Negative alerted (observed false alarm) | 0/25 | 0% |
| Negative returned no leak | 25/25 | 100% |
| Negative inconclusive | 0/25 | 0% |

Inconclusive runs remain separate from explicit misses. There were two positive
non-detections in total. These are small, one-host, potentially correlated samples;
the percentages are descriptive, not estimated deployment sensitivity/specificity.
The 40-run study did not include injected jitter; T2 supplies that separate case.

Engine-call latency across the study was **6.816 ms median**, **23.222 ms p95**
(nearest rank), range **3.003-49.132 ms**. It includes warm-up, sampling and
statistics, and excludes HTTP, database, report export and browser rendering.
The QA runner's wall times were **42.078 s** for pytest and **1.468 s** for the
six-case evaluation; those include subprocess overhead. See the raw
[measurement](evidence/measurements.json) and [QA](evidence/qa-summary.json) records.

## Findings, limits and ethics

Member D fixed actual-byte body-size enforcement, added safe `.env`
initialization, made smoke cleanup failures fail the gate, removed a misleading
hard-coded database path from admin setup output, and made the Docker evidence
directory writable by the application user. Regression tests and the bounded
Docker inspection are listed in [Part 4.4](../document.md#44-defects-found-and-corrected).

The lab accepts fixed local synthetic fixtures, not arbitrary network targets or
real credentials. Keep local secrets and databases private, use sanitized
exports, and obtain authorization before applying side-channel techniques to any
other system. Preserve evidence honestly: retain misses/inconclusive results,
report actual intervals, and do not alter thresholds solely to present success.

OS scheduling, runtime, CPU power state, sample size and shared host load can
change the results. Repeated comparisons also create false-alarm opportunities;
this lab does not claim a multiple-testing correction or a production detector.
The plotted normal curves approximate summaries; raw histogram bins are also
available. Same-origin sessions and localhost binding support the local demo,
but the supplied deployment is not a production hosting configuration.

Docker/Linux execution, container-volume ownership and a new interactive
browser/accessibility rehearsal remain outside this verification record. No
screenshots or rehearsal completion are claimed. The earlier Member C interface
account in the shared document was not independently repeated by Member D.

## Reproduction

Follow [fresh setup](../PACKAGING.md), then run sequentially:

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m scripts.qa
.\.venv\Scripts\python.exe -m scripts.smoke
.\.venv\Scripts\python.exe -m docs.evidence.collect_measurements --output artifacts/qa/measurements.json
```

Keep the generated summary, JUnit report and measurement JSON together with the
revision and environment. New measurements should not replace this historical
snapshot without documenting the new run. Dependency installation requires
network access unless the wheels are already available; normal measurements
use local fixtures. See [user/admin operation](USER_GUIDE.md) and the
[14-minute demo](DEMO.md).

## Delivery checklist

- [x] Source, pinned dependency snapshot and setup guide included.
- [x] Architecture/data-flow and mapped threats present in Parts 1-2.
- [x] Automated test plan/results, T1-T6, T-final and quantitative evidence included.
- [x] Sanitized synthetic sample report and evidence provenance included.
- [x] User/admin instructions, limitations, ethics and demo script included.
- [ ] Team rehearses the interactive browser flow and checks responsive charts,
  keyboard navigation, focus visibility and error announcements on its demo laptop.
- [ ] Team checks final submission names/member names and the instructor's format.
- [ ] Optional Docker path is run on an available Docker host before claiming support
  was verified there; the Python path is the verified demonstration path.
