import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app import models
from backend.app.database import Base


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