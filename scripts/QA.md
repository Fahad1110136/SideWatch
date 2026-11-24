# QA automation

From the project root, after installing `requirements.txt`, run:

```powershell
.\.venv\Scripts\python.exe -m scripts.qa
```

On other platforms, use your environment's `python -m scripts.qa`.
No running server or existing administrator is needed. The command uses the
same Python environment for both checks, runs from the project root, and supplies
a temporary database and generated test secret to the subprocesses. It does not
change `.env` or the application's database.

Each invocation creates a separate folder under `artifacts/qa/` containing:

- `summary.md`: human-readable overall status and counts.
- `summary.json`: status, commands, durations, UTC timestamps, Python/OS/package
  versions, Git revision and whether the working tree had changes.
- `pytest.xml`: JUnit test evidence.
- `pytest.stdout.log` and `pytest.stderr.log`: test runner output.
- `evaluation.stdout.log`: the T1-T6 JSON report, including inputs, expected and
  actual results, evidence and pass/fail status.
- `evaluation.stderr.log`: evaluation diagnostics.

Exit code `0` means both commands succeeded and their reports passed validation.
Exit code `1` means a check failed, timed out, or produced missing/invalid evidence.
Invalid command-line arguments return `2`. Evaluation still runs if pytest fails,
so both sets of evidence are available. A run with no passing tests fails.

Each check has a 300-second timeout. Override it or the evidence parent directory:

```powershell
.\.venv\Scripts\python.exe -m scripts.qa --timeout 600 --output-dir artifacts/qa
```

Generated evidence is excluded from Git and Docker builds by default. Review logs
before sharing them; diagnostic output can contain local paths and test details.
Use a clean committed checkout for final evidence so its revision identifies the
tested source. Package versions are recorded for context; dependency locking and
fresh-install verification are separate packaging work.

## Interpretation

The runner requires all executed tests and all six evaluation cases to pass.
This is stricter than the proposal's minimum test pass percentage, but does not
certify the absence of critical security defects. The existing T1-T6 pass checks
validate engine behavior and fixture wiring. Inspect and interpret the actual
measurements separately. A seed reproduces scheduling and injected jitter, not
wall-clock timing; a clean verdict does not prove constant-time behavior.

This command does not yet perform browser QA, real process-restart checks, or
fresh-install/Docker verification. Those belong to the subsequent QA commits.
