"""Alembic environment for the durable tables (RequestsBase). Never touches the seed tables."""

from alembic import context

from app.core.config import get_settings
from app.core.db import RequestsBase, make_engine

target_metadata = RequestsBase.metadata


def run_migrations_online() -> None:
    # scripts/import_data.py passes its own connection; the alembic CLI uses DATABASE_URL.
    connection = context.config.attributes.get("connection")
    if connection is not None:
        _run(connection)
        return
    engine = make_engine(get_settings().database_url)
    with engine.connect() as conn:
        _run(conn)
        conn.commit()
    engine.dispose()


def _run(connection) -> None:  # type: ignore[no-untyped-def]
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,  # SQLite needs batch mode for ALTER TABLE
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    raise SystemExit("Offline mode is not used; run against a database.")
run_migrations_online()
