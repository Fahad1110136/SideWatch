# Evidence index and provenance

These are historical local observations from application revision
`d651d53509b0cc1b9e5067c7804caec6a2af8de1`, the third Member D commit. Collection
used the fresh Python 3.12 environment described in [PACKAGING.md](../../PACKAGING.md).
The working tree had local documentation changes; summaries preserve that fact.
The final documentation commit does not change application behavior.

| File | Purpose and source |
|---|---|
| [qa-summary.json](qa-summary.json) | Latest final `scripts.qa` run: commands, environment, durations, test/evaluation totals and status. Absolute project command paths were replaced with `PROJECT_ROOT`/`python`. |
| [pytest.xml](pytest.xml) | JUnit results from that same run, containing 172 passing test cases. Hostname attributes were removed; names, counts, durations and outcomes were retained. |
| [evaluation.json](evaluation.json) | Unmodified JSON stdout from that run's `engine.evaluation`: T1-T6 inputs, expected/actual results, evidence and case status. |
| [smoke-summary.json](smoke-summary.json) | Final successful `scripts.smoke` run against the normal application with disposable local data. |
| [dependency-check.json](dependency-check.json) | Direct pip-check output, pinned-version comparison and isolated-venv status from the fresh installation. |
| [sample-report.json](sample-report.json) | Sanitized synthetic report exported by the same smoke run. Existing generated record IDs/digests are retained for integrity verification; no real user data/passwords/session tokens are included. |
| [measurements.json](measurements.json) | Forty exploratory measured runs and explicitly defined observational error/latency metrics. No raw credentials, network targets or local filesystem paths are collected. |
| [collect_measurements.py](collect_measurements.py) | Exact protocol for regenerating the exploratory study. Its SHA-256 digest is stored in the measurement record. |
| [manifest.json](manifest.json) | SHA-256 digests of the committed evidence/protocol files to detect accidental edits. This is an integrity inventory, not a signed attestation. |

Raw machine-local runner folders remain under ignored `artifacts/qa/` and
`artifacts/packaging/`. They are not required to read the committed evidence.
No `.env`, database, password or active session token has been copied into this
directory. Numeric timing evidence, rule settings, public fixture IDs and
non-secret schedule/jitter hashes are intentionally preserved.
Text snapshots use LF line endings, enforced by `.gitattributes`, so checkout
conversion does not invalidate the digest inventory. JSON values and test
outcomes are unchanged by line-ending normalization.

All evidence timestamps are UTC. For the user's Asia/Karachi timezone add five
hours; the final records were collected on **25 November 2026 PKT**. Wall-clock
values are observations, not fixtures that a later run must reproduce exactly.

To regenerate without overwriting this snapshot, use the commands in
[the QA report](../QA_REPORT.md#reproduction). The synthetic sample report's digest
can be checked by removing `integrity`, serializing the remaining object with
sorted keys and compact separators, and computing SHA-256. The digest inventory
does not establish authorship; changing both a file and its manifest is possible.
