"""
Database configuration module.

This module sets up the SQLAlchemy engine and session for interacting with a
PostgreSQL database. Configuration is read from environment variables so
that the connection details can be provided at runtime (e.g. via
docker‑compose). A helper function `get_db` is provided for FastAPI
dependencies, yielding a database session and ensuring it is closed after
use.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def _build_db_url() -> str:
    """Assemble the SQLAlchemy database URL from environment variables."""
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    host = os.getenv("POSTGRES_HOST", "db")
    port = os.getenv("POSTGRES_PORT", "5432")
    db_name = os.getenv("POSTGRES_DB", "privacyguard")
    return f"postgresql://{user}:{password}@{host}:{port}/{db_name}"


# Create the SQLAlchemy engine.  `pool_pre_ping=True` helps to avoid
# stale connections when the database restarts.
SQLALCHEMY_DATABASE_URL = _build_db_url()
engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)

# SessionLocal is a factory for database sessions.  Setting
# `autocommit=False` and `autoflush=False` gives us explicit control over
# transaction boundaries.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """
    FastAPI dependency that provides a SQLAlchemy session.

    Yields:
        Session: a new SQLAlchemy session bound to the engine.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()