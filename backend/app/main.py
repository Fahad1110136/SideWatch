# from contextlib import asynccontextmanager

# from fastapi import FastAPI

# from backend.app.api import audit, auth, rules, submissions, users
# from backend.app.config import settings
# from backend.app.core.errors import register_exception_handlers
# from backend.app.core.middleware import BodySizeLimitMiddleware, SecurityHeadersMiddleware
# from backend.app.database import SessionLocal, init_db
# from backend.app.repositories import rule_repo
# from backend.app.services import recovery_service


# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     init_db()
#     with SessionLocal() as db:
#         rule_repo.seed_defaults(db)
#         recovery_service.run_startup_checks(db)
#     yield


# app = FastAPI(title="SideWatch", docs_url="/api/docs", lifespan=lifespan)
# register_exception_handlers(app)
# # The last middleware added is the outermost, so headers also cover 413/411 responses.
# app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_body_bytes)
# app.add_middleware(SecurityHeadersMiddleware, hsts=settings.app_env == "production")
# app.include_router(auth.router)
# app.include_router(users.router)
# app.include_router(audit.router)
# app.include_router(submissions.router)
# app.include_router(submissions.fixtures_router)
# app.include_router(rules.router)


# @app.get("/api/health")
# def health():
#     return {"status": "ok"}






from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.app.api import audit, auth, rules, submissions, users
from backend.app.config import settings
from backend.app.core.errors import register_exception_handlers
from backend.app.core.middleware import BodySizeLimitMiddleware, SecurityHeadersMiddleware
from backend.app.core.startup import enforce_secure_settings
from backend.app.database import SessionLocal, init_db
from backend.app.repositories import rule_repo
from backend.app.services import recovery_service

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    enforce_secure_settings(settings)      # production refuses insecure config
    init_db()
    with SessionLocal() as db:
        rule_repo.seed_defaults(db)
        recovery_service.run_startup_checks(db)
    yield


app = FastAPI(title="SideWatch", docs_url="/api/docs", lifespan=lifespan)
register_exception_handlers(app)
# The last middleware added is the outermost, so headers also cover 413/411 responses.
app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_body_bytes)
app.add_middleware(SecurityHeadersMiddleware, hsts=settings.app_env == "production")
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(audit.router)
app.include_router(submissions.router)
app.include_router(submissions.fixtures_router)
app.include_router(rules.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


# Must stay LAST: it catches every path the API routes didn't match.
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")