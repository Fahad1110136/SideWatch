# SideWatch demonstration and rehearsal

Target duration: **14 minutes**, with one minute spare. This is a reproducible
script, not a claim that the team has completed a live rehearsal. Use the verified
Python path on the presentation laptop; Docker is optional and unverified here.

## Prepare before presenting

Follow [setup](../PACKAGING.md), create the first admin, and use **Users** to
create an operator and a viewer with private demo passwords. Do not show the
password prompts, `.env`, cookies or CSRF tokens on screen. Keep all runs on
localhost and use synthetic fixtures only. Note current thresholds before any
demo change, so they can be restored with a recorded administrative action.

Run the following sequentially before the session and keep their evidence ready:

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m scripts.qa
.\.venv\Scripts\python.exe -m scripts.smoke
```

Then start the ordinary application:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000/. Close timing-heavy applications, enlarge the browser
for readable charts, and retain [the evidence snapshot](evidence/README.md) as a
backup if timing observations are inconclusive. Do not rerun indefinitely until
a preferred verdict appears. Respect the submission rate limit (20/minute).

## Presentation sequence

| Time | Action | Explain/show |
|---|---|---|
| 0:00-1:00 | Introduce the problem and architecture | A local lab compares early-exit code with `hmac.compare_digest`; show the trust-boundary diagram in Part 1. |
| 1:00-2:00 | Sign in as operator; open New measurement | Show validated settings and role-appropriate navigation. Use 300 samples, 20 warm-ups and seed 2026. |
| 2:00-4:00 | Run Prefix sweep with both implementations | Show the six runs, prefix chart and comparison evidence (T3/T4). Noise can obscure a short prefix; inspect actual intervals. |
| 4:00-5:00 | Open a result and its recommendations | Explain the verdict, p-value, effect-size condition, CI, histogram and mitigation (FR-3/5/6, T5). |
| 5:00-6:00 | Compare 30 vs 300 samples for the one-byte fixture | Demonstrate T1. A larger sample often narrows uncertainty, but no fixed ratio or verdict is promised. |
| 6:00-7:30 | Run the four-byte jitter fixture, then Run again with the same seed | Show jitter evidence and matching schedule digest (T2/T6). Explain why measured nanoseconds still vary. |
| 7:30-8:30 | Use History filters and compare two runs | Show traceable inputs/settings and that repeated submissions are distinct records. |
| 8:30-9:30 | Submit invalid JSON through the browser console using the snippet below | Show safe 422 without a leaked input/stack trace. The browser form normally prevents such input before submission. |
| 9:30-10:30 | Sign in as viewer and issue the valid submission snippet | Show server-side 403. Sign out; return as admin and show its denial audit event. |
| 10:30-11:30 | Change one rule with confirmation; run another measurement | Show rule version/audit entry and the new result's threshold snapshot. Restore the original setting afterward with confirmation. |
| 11:30-12:30 | Export a completed result and verify the audit chain | Show sanitized report, reasons and digest. Explain that a digest is not a signature. |
| 12:30-13:30 | Stop/restart the ordinary server; reopen history | Show preserved results. Point to the automated crash/recovery test for interruption during an engine call; normal runs may finish too quickly to interrupt reliably. |
| 13:30-14:00 | Show QA results and limitations | 172 passing tests, six harness cases, exploratory detection/error figures, noise limits and localhost-only ethics. |

## Safe misuse snippets

Use these only on the project's own localhost page in browser developer tools.
Each snippet obtains a CSRF token without printing it. Token refresh may cause
the main interface to refresh its token on the next action, which it supports.

While signed in as the operator, malformed JSON should produce **422**:

```javascript
(async () => {
  const { csrf_token } = await fetch('/api/auth/csrf').then(r => r.json());
  const response = await fetch('/api/submissions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf_token },
    body: '{invalid-json'
  });
  console.log(response.status, await response.json());
})();
```

While signed in as the restricted viewer, a valid measurement request should
produce **403 ACCESS_DENIED**, even if the browser hides its submission screen:

```javascript
(async () => {
  const { csrf_token } = await fetch('/api/auth/csrf').then(r => r.json());
  const response = await fetch('/api/submissions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf_token },
    body: JSON.stringify({
      label: 'Viewer denial demo', implementation: 'vulnerable',
      fixture_id: 'prefix_4', sample_size: 300, warmup_runs: 20, seed: 2026
    })
  });
  console.log(response.status, await response.json());
})();
```

Malformed-input and viewer-denial audit behavior differ: the viewer's role denial
is logged; not every schema-validation failure produces a security audit event.
Do not claim that invalid JSON necessarily creates an audit event.

## Manual rehearsal checklist

- [ ] Complete the sequence within 10-15 minutes on the actual presentation laptop.
- [ ] Check sign-in/out, role menus, run controls, charts, history, export and confirmations.
- [ ] Check charts and tables at a narrow browser width and normal desktop width.
- [ ] Use the keyboard to reach controls and confirmations; check visible focus,
  readable labels and announced errors. Record any defect rather than claiming a
  formal accessibility audit.
- [ ] Confirm a completed run/history and audit verification after restart.
- [ ] Confirm admin and operator understand the distinction between a harness pass,
  observed leakage, inconclusive evidence and proof of constant-time behavior.
- [ ] Keep sanitized evidence ready; exclude passwords, personal records, `.env`
  and local databases from the submitted archive.
