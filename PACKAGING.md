# Local setup and packaging verification

The verified baseline is Python 3.12 on Windows x64. `requirements.lock` pins the
installed direct and transitive dependencies used for verification. It is a
version snapshot, without artifact hashes; other Python versions and platforms
need their own verification. `requirements.txt` retains the development ranges.

## Fresh setup

From PowerShell in the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m scripts.init_env
.\.venv\Scripts\python.exe -m scripts.seed_admin --username admin
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

The administrator password is entered at hidden prompts. Open
http://127.0.0.1:8000/ and sign in. No frontend build, Node.js, or paid service
is required. The interface's assets are served by the local application.
On Linux/macOS, use `.venv/bin/python` instead of the Windows executable path.

`scripts.init_env` creates `.env` with a generated secret only if the file does
not exist. It preserves an existing file byte for byte. It does not repair weak
existing settings: review those before first use. Keep the existing secret when
restarting an installation with data; sessions and the audit chain depend on it.
Never include `.env`, local databases, or virtual environments in a submission.

Stop with Ctrl+C and restart with the same Uvicorn command and configuration.
Back up `data/sidewatch.db` while the application is stopped, together with a
private copy of its configuration. To restore, stop the app, restore the database
and matching secret, then restart and verify the audit chain as administrator.
Do not reset an existing database merely to repeat a demo.

## Automated packaging smoke check

After installing dependencies, stop any timing-heavy background work and run:

```powershell
.\.venv\Scripts\python.exe -m scripts.smoke
.\.venv\Scripts\python.exe -m scripts.qa
```

The smoke check starts the real application with a disposable database, generated
credentials and localhost ports selected by the OS. It supplies an automated
password-prompt callback to the real admin-seeding CLI, then checks:

1. Admin creation, health endpoint, frontend HTML/CSS/JavaScript and page CSP.
2. Login, CSRF-authenticated measurement, explainable result and histogram.
3. Sanitized report export, recomputed SHA-256 digest and audit-chain verification.
4. Actual process restart with persisted result, session and audit chain.
5. Logout followed by rejected authenticated access.

It uses the normal engine without the fault hooks in the security test server.
It leaves `.env` and the application's database alone and cleans up its child
processes and temporary database. Proxy environment settings are ignored by its
localhost HTTP clients. Successful exit is `0`; failed checks return `1`.
The command retrieves frontend assets over HTTP; it does not drive a browser or
verify JavaScript rendering, accessibility or responsive layout.

Evidence is saved in a new `artifacts/packaging/smoke-*` directory: `summary.json`,
`seed.log`, two server logs and a sanitized `sample-report.json`. Use `--output-dir PATH` to
choose another parent folder. Evidence includes the Python/OS/package versions
and Git revision; a dirty working tree is identified. Review logs before sharing.
The separate QA runner records automated tests and T1-T6 measurements under
`artifacts/qa/`; see [the QA guide](scripts/QA.md).

For an independent installation check without replacing your existing `.venv`:

```powershell
python -m venv artifacts/packaging/venv
.\artifacts\packaging\venv\Scripts\python.exe -m pip install --no-cache-dir -r requirements.lock
.\artifacts\packaging\venv\Scripts\python.exe -m pip check
.\artifacts\packaging\venv\Scripts\python.exe -m scripts.smoke
.\artifacts\packaging\venv\Scripts\python.exe -m scripts.qa
```

## Docker path

Docker is optional. Its Dockerfile installs the pinned dependency snapshot and
runs as the `sidewatch` user, with writable data and evidence directories. Compose
publishes only `127.0.0.1:8000` and retains the SQLite database in `sidewatch-data`.

Docker was unavailable on the verification machine. A Linux image build,
container startup, volume ownership and container restart have **not been run**.
Run these checks on a machine with Docker Desktop/Compose before claiming the
Docker path is verified:

```powershell
python -m scripts.init_env
docker compose config --quiet
docker compose up --build -d --wait
docker compose exec app python -m scripts.seed_admin --username admin
docker compose exec app python -m pip check
docker compose exec app python -m scripts.smoke
docker compose exec app python -m scripts.qa
docker compose restart app
```

Verify your own measurement/history and audit chain through the browser after
the container restart. Stop with `docker compose down` to retain the named volume.
The smoke command's database is disposable, so also verify the Compose volume
with a normal application measurement. This Compose configuration is for local
demonstrations. The base image tag is not pinned by digest, so rebuilding is not
a byte-for-byte image reproduction guarantee.
