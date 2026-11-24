# SideWatch user and administrator guide

Start the local app using [the packaging guide](../PACKAGING.md), then open
http://127.0.0.1:8000/. Use an account created for your role. The first admin is
created with `python -m scripts.seed_admin --username admin`; its password is
entered privately and is not supplied by this repository.

## Sign in and run a measurement

After signing in, an administrator or operator opens **New measurement**.
Choose **Single run**, an implementation and a synthetic guess. Use a sample
count between 30 and 5000, warm-up count between 0 and 500, and optionally a seed
between 0 and 2147483647. Give the run a short label and select **Run measurement**.
For a first demonstration, try the vulnerable comparison with four correct
bytes, 300 samples, 20 warm-ups and seed 2026. A short or noisy run may miss a
deliberate leak; keep the observed result rather than assuming it must detect one.

**Prefix sweep** measures the 1-, 4- and 32-byte fixtures with one or both
implementations. **Face-off** runs the vulnerable and constant-time implementations
against the same fixture. Every run uses the no-match input as its control;
the browser omits it from the selectable guesses.

## Read and compare results

The result includes a verdict, severity, evidence, statistical checks and
recommended action. Inspect the p-value, effect size, interval and histogram.
An interval crossing zero can mean the observed gap is not distinguishable from
noise. The 99% confidence level describes the interval method, not the probability
that a leak exists. A clean result does not establish constant-time behavior.

Use **History** to filter results and select two for comparison. **Run again**
restores the earlier measurement inputs; using the same seed reproduces the
schedule and simulated jitter, not exact nanoseconds. The comparison view can
show whether schedule digests match. Operators see their own runs; viewers see
completed runs under the server's visibility policy.

Use the result's export action to download a sanitized JSON report. It includes
the input settings, rule/engine details, reasons, evidence and integrity digest.
An example is [the synthetic sample report](evidence/sample-report.json).
The digest covers every field except `integrity`, using sorted compact JSON.
It detects a changed report when compared with the recorded digest; it is not a
digital signature or proof of authorship. Admins can also review the export's
digest in the audit event.

## Administrator tasks

| Task | Procedure |
|---|---|
| Create an operator/viewer | Open **Users**, create a unique username and strong password, and select the least-privileged role required. Share credentials privately. |
| Deactivate an account | Use its activation control and confirm. Existing sessions are revoked. Self-deactivation is rejected. |
| Reset another user's password | Use **Users**, enter a new strong password and confirm. Existing sessions are revoked and lockout is cleared. Use **Account** for your own password. |
| Change analysis settings | Open **Rules**, note the existing value, change one threshold within its bounds and confirm. New runs retain the setting used; earlier results are not reinterpreted. |
| Check activity | Open **Audit log**, filter actions/outcomes, expand details and run hash-chain verification. Include denied actions and exports in the review. |
| Back up or restore | Stop the application and follow the database-plus-matching-secret instructions in [PACKAGING.md](../PACKAGING.md). Verify the audit chain after restore. |

An operator may read rules but cannot edit them. A viewer cannot submit, change
rules or administer users/audit. Hiding a browser control is only a convenience;
the server rejects unauthorized calls directly.

## Errors and recovery

Use the on-screen message and request reference when reporting an error. A 401
requires signing in again; a 403 can indicate a role or CSRF denial. A 404 may
mean a record does not exist or is not visible to the account. A 422 means the
request failed validation; a 413 means it exceeded the body limit. A 429 means
the rate limit was reached: wait for the window rather than disabling protection.

`ENGINE_FAILED` means the run failed safely and has no fabricated result. Repeat
after checking the server diagnostics. Following an interrupted server run,
startup marks outstanding work `INTERRUPTED_BY_RESTART`; create a new measurement
and retain the failed record for traceability. Restart using the same secret and
database. Do not delete the database or change the secret as a routine workaround.

Change your own password under **Account** and sign out when finished. Never
paste real credentials into measurement fields or use external systems as targets.
