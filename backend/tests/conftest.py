import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app import models
from backend.app.database import Base


from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool

from backend.app.core.rate_limit import limiter
from backend.app.database import get_db
from backend.app.main import app


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session

@pytest.fixture
def user(db):
    u = models.User(username="alice", password_hash="x", role="operator")
    db.add(u)
    db.commit()
    return u

@pytest.fixture
def api_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session

@pytest.fixture
def client(api_db):
    limiter.reset()
    app.dependency_overrides[get_db] = lambda: api_db
    yield TestClient(app)
    app.dependency_overrides.clear()