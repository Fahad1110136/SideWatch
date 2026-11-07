# from contextlib import asynccontextmanager

# from fastapi import FastAPI

# from backend.app.api import audit, auth, users
# from backend.app.core.errors import register_exception_handlers
# from backend.app.database import init_db


# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     init_db()
#     yield


# app = FastAPI(title="SideWatch", docs_url="/api/docs", lifespan=lifespan)
# register_exception_handlers(app)
# app.include_router(auth.router)
# app.include_router(users.router)
# app.include_router(audit.router)


# @app.get("/api/health")
# def health():
#     return {"status": "ok"}





from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.app.api import audit, auth, rules, submissions, users
from backend.app.core.errors import register_exception_handlers
from backend.app.database import SessionLocal, init_db
from backend.app.repositories import rule_repo


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    with SessionLocal() as db:
        rule_repo.seed_defaults(db)
    yield


app = FastAPI(title="SideWatch", docs_url="/api/docs", lifespan=lifespan)
register_exception_handlers(app)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(audit.router)
app.include_router(submissions.router)
app.include_router(submissions.fixtures_router)
app.include_router(rules.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}