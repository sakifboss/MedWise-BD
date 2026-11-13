"""Run the Alembic migrations for the durable tables (request log, data reports, doctor tables).

scripts/import_data.py calls upgrade_durable_tables() before it rebuilds the seed tables, so the
Render build and the Docker start need no extra command. Only row counts are reported (never rows).
"""

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, func, inspect, select, table

from app.core.config import BACKEND_DIR

DURABLE_TABLES = (
    "medicine_requests",
    "data_reports",
    "doctors",
    "doctor_chambers",
    "doctor_sessions",
    "doctor_password_resets",
)


def _count(engine: Engine, name: str) -> int | None:
    if not inspect(engine).has_table(name):
        return None
    with engine.connect() as conn:
        return conn.execute(select(func.count()).select_from(table(name))).scalar_one()


def upgrade_durable_tables(engine: Engine) -> dict[str, tuple[int | None, int | None]]:
    """Upgrade to the latest revision. Returns {table: (rows before, rows after)}."""
    before = {name: _count(engine, name) for name in DURABLE_TABLES}
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    after = {name: _count(engine, name) for name in DURABLE_TABLES}
    lost = [n for n in DURABLE_TABLES if (before[n] or 0) > (after[n] or 0)]
    if lost:
        raise RuntimeError(f"Rows disappeared during the migration: {', '.join(lost)}")
    return {name: (before[name], after[name]) for name in DURABLE_TABLES}
