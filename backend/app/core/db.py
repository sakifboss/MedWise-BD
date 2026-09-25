from collections.abc import Iterator
from typing import Any

from sqlalchemy import Engine, create_engine, event, make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def _enable_sqlite_foreign_keys(dbapi_connection: Any, _record: Any) -> None:
    # SQLite ignores foreign keys unless enabled per connection.
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def normalize_database_url(url: str) -> str:
    """Clean up a pasted connection string and name the installed psycopg 3 driver.

    Tolerates common copy-paste mistakes from hosting dashboards: surrounding whitespace
    or quotes, a leading `DATABASE_URL=`, or Neon's `psql '...'` command wrapper.
    """
    cleaned = url.strip().removeprefix("DATABASE_URL=").strip()
    if cleaned.startswith("psql "):
        cleaned = cleaned.removeprefix("psql ").strip()
    cleaned = cleaned.strip("'\"").strip()
    for prefix in ("postgres://", "postgresql://"):
        if cleaned.startswith(prefix):
            return "postgresql+psycopg://" + cleaned.removeprefix(prefix)
    return cleaned


def _describe_bad_url(url: str) -> str:
    """Explain what's wrong without echoing the URL (it contains the password)."""
    scheme = url.split("://", 1)[0] if "://" in url else None
    if scheme is None:
        return "it does not contain '://'. It should look like postgresql://user:password@host/db"
    if len(scheme) > 25 or " " in scheme:
        return "there is extra text before 'postgresql://'. Paste only the URL itself"
    return f"unsupported scheme '{scheme}'. Use a postgresql:// URL"


def make_engine(database_url: str) -> Engine:
    url = normalize_database_url(database_url)
    try:
        make_url(url)
    except ArgumentError:
        raise ValueError(
            f"DATABASE_URL is not a valid database URL: {_describe_bad_url(url)}"
        ) from None
    if url.startswith("sqlite"):
        engine = create_engine(url, connect_args={"check_same_thread": False})
        event.listen(engine, "connect", _enable_sqlite_foreign_keys)
        return engine
    # Serverless Postgres (Neon) drops idle connections; check before reuse.
    # prepare_threshold=None: no server-side prepared statements, which break behind
    # a transaction-mode pooler such as Neon's PgBouncer endpoint.
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=300,
        connect_args={"prepare_threshold": None},
    )


engine = make_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency that yields a session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
