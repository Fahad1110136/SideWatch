# from fastapi import FastAPI

# app = FastAPI(title="SideWatch", docs_url="/api/docs")


# @app.get("/api/health")
# def health():
#     return {"status": "ok"}

from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.app.core.errors import register_exception_handlers
from backend.app.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="SideWatch", docs_url="/api/docs", lifespan=lifespan)
register_exception_handlers(app)


@app.get("/api/health")
def health():
    return {"status": "ok"}