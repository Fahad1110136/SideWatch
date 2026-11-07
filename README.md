# SideWatch

SideWatch is a local timing-leakage measurement lab. It compares a deliberately
vulnerable early-exit byte comparison with Python's
`hmac.compare_digest`, and returns an explainable statistical result.

> This is a local educational microbenchmark, not a production security scanner
> or proof that an implementation is constant-time. Results can vary with
> hardware, runtime, and system load.

## Run with Docker

Requirements: Docker Desktop with Docker Compose.

From PowerShell, in the project directory:

```powershell
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Copy the generated value into `.env` as the value of `SECRET_KEY`, replacing
the example value. Keep `.env` private; it is git-ignored.

Build and start the app:

```powershell
docker compose up --build -d
```

Open:

- App: <http://127.0.0.1:8000/>
- Interactive API documentation: <http://127.0.0.1:8000/api/docs>
- Health check: <http://127.0.0.1:8000/api/health>

The API and engine can be exercised from the interactive documentation. Create
the first administrator from PowerShell; the password is requested interactively:

```powershell
docker compose run --rm --no-deps app python -m scripts.seed_admin --username admin
```

The homepage is currently a placeholder, so use `/api/docs` to sign in and run
measurements. The SQLite database is stored in the `sidewatch-data` Docker
volume and persists when the container is stopped or removed.

Stop the service without deleting its data:

```powershell
docker compose down
```

## Run the tests

Run the complete test suite in the Docker image:

```powershell
docker compose run --rm --no-deps app pytest -q -p no:cacheprovider
```

## Timing engine

The engine compares each selected fixture against the `no_match` control using
paired timing samples. Available fixtures are:

| Fixture | Description |
|---|---|
| `no_match` | Control input that differs at the first byte |
| `prefix_1` | Input matching one leading byte |
| `prefix_4` | Input matching four leading bytes |
| `full_match` | Input matching all 32 bytes |
| `prefix_1_jitter` | One-byte prefix with controlled measurement jitter |
| `prefix_4_jitter` | Four-byte prefix with controlled measurement jitter |

Results include a paired statistical test, effect size, confidence interval,
chart-ready histograms, and mitigation guidance. Use the same seed to reproduce
the randomized measurement schedule and simulated jitter; actual wall-clock
measurements will still vary.

## Project layout

- `backend/` — FastAPI application, authentication, persistence, and tests
- `engine/` — timing comparison implementations and safe demo fixtures
- `scripts/` — administrative setup utilities
- `frontend/` — static homepage
- `document.md` — project proposal mapping, architecture, and implementation details
