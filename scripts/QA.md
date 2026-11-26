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

## Security and restart checks

The pytest stage also runs `backend/tests/test_security_live.py` against real
Uvicorn subprocesses on dynamically assigned localhost ports. Each test creates
its own temporary SQLite database, secret and accounts, without using the local
application database or administrator. HTTP clients ignore proxy environment
settings so these requests stay on localhost. No server needs to be started manually.

These checks cover malformed and oversized input, anonymous and restricted-viewer
denials, repeated submissions, failed engine output, exception handling, and a
successful measurement after a failure. The restart check kills a server during
a measurement, starts it again against the same temporary database and secret,
and verifies recovery, preserved results and rule versions, accepted active
sessions, rejected revoked sessions and audit-chain integrity. A second restart
checks recovery is not duplicated.

`backend/tests/live_server.py` is a dedicated test entry point. It injects an
engine exception, malformed output and a blocked measurement for deterministic
failure tests; normal `no_match` runs still use the real engine. These hooks are
not in the application entry point. The restart test demonstrates recovery from
an in-flight engine interruption; it does not simulate interruption during every
database write. Child logs live in pytest's temporary test directories and are
shown on startup failures. Processes and clients are cleaned up even on failure.

`backend/tests/test_security_qa.py` additionally checks session-bound CSRF tokens
and counts actual ASGI request bytes, including streams with absent or understated
Content-Length. The size guard rejects excessive bodies before the API runs,
accepts a body exactly at the limit and preserves its bytes. HTTP protocol parsers
may independently reject invalid framing before it reaches the application.

For fresh-install verification and the normal application's packaging smoke
command, see [the packaging guide](../PACKAGING.md). Browser interaction remains
a separate manual check; Docker verification requires an available Docker runtime.
