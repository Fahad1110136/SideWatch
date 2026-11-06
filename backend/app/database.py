# # from sqlalchemy import create_engine
# # from sqlalchemy.orm import DeclarativeBase, sessionmaker

# # from backend.app.config import settings

# # connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
# # engine = create_engine(settings.database_url, connect_args=connect_args)
# # SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


# # class Base(DeclarativeBase):
# #     pass


# # def get_db():
# #     db = SessionLocal()
# #     try:
# #         yield db
# #     finally:
# #         db.close()


# # def init_db() -> None:
# #     from backend.app import models  # noqa: F401  (registers tables)
# #     Base.metadata.create_all(engine)

# from unittest.mock import Base

# from sqlalchemy import engine


# def init_db() -> None:
#     from pathlib import Path
#     from backend.app import models  # noqa: F401  (registers tables)

#     Path("data").mkdir(exist_ok=True)
#     Base.metadata.create_all(engine)

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from backend.app.config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from backend.app import models  # noqa: F401  (registers tables)

    Path("data").mkdir(exist_ok=True)
    Base.metadata.create_all(engine)