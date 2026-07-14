"""SQLite engine/session setup."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base


def make_engine(database_path: Path):
    database_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{database_path}", future=True)
    Base.metadata.create_all(engine)
    return engine


def make_session_factory(database_path: Path) -> sessionmaker[Session]:
    engine = make_engine(database_path)
    return sessionmaker(bind=engine, future=True)
