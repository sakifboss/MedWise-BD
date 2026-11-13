"""Alembic for the durable tables (R1; doctor tables from R2). The first run on the live database
(tables already there, with rows, and no Alembic yet) must keep every row, and so must 0003."""

from datetime import date
from pathlib import Path

from sqlalchemy import Engine, inspect, text

from app.core.config import get_settings
from app.core.db import make_engine
from app.core.migrations import upgrade_durable_tables
from scripts.import_data import run_import


def _engine(tmp_path: Path) -> Engine:
    return make_engine(f"sqlite:///{(tmp_path / 'db.sqlite').as_posix()}")


HEAD = "0004"
DOCTOR_TABLES = (
    "doctors",
    "doctor_chambers",
    "doctor_sessions",
    "doctor_password_resets",
    "doctor_templates",
)
NEW_DOCTOR_TABLES = {name: (None, 0) for name in DOCTOR_TABLES}
EMPTY_DOCTOR_TABLES = {name: (0, 0) for name in DOCTOR_TABLES}


def _version(engine: Engine) -> str:
    with engine.connect() as conn:
        return conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()


def test_upgrade_on_an_empty_database(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    rows = upgrade_durable_tables(engine)
    assert rows == {"medicine_requests": (None, 0), "data_reports": (None, 0), **NEW_DOCTOR_TABLES}
    columns = {c["name"] for c in inspect(engine).get_columns("data_reports")}
    assert "brand_code" in columns
    assert _version(engine) == HEAD
    engine.dispose()


def _make_live_like(engine: Engine) -> None:
    """The live database before R1: both tables exist with rows, no alembic_version."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE medicine_requests (id INTEGER PRIMARY KEY,"
                " query VARCHAR(80) NOT NULL, source VARCHAR(20) NOT NULL,"
                " requested_on DATE NOT NULL)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE data_reports (id INTEGER PRIMARY KEY, brand_id INTEGER NOT NULL,"
                " brand_name VARCHAR(200) NOT NULL, manufacturer VARCHAR(200) NOT NULL,"
                " strength VARCHAR(50) NOT NULL, dosage_form VARCHAR(50) NOT NULL,"
                " reason VARCHAR(30) NOT NULL, reported_on DATE NOT NULL)"
            )
        )
        for q in ("Fexo", "Fexo", "Qwzxyfexo", "Romycin"):
            conn.execute(
                text(
                    "INSERT INTO medicine_requests (query, source, requested_on)"
                    " VALUES (:q, 'search', :d)"
                ),
                {"q": q, "d": date(2026, 11, 10)},
            )
        conn.execute(
            text(
                "INSERT INTO data_reports (brand_id, brand_name, manufacturer, strength,"
                " dosage_form, reason, reported_on) VALUES (22, 'Seclo', 'Square', '20 mg',"
                " 'capsule', 'wrong_price', :d)"
            ),
            {"d": date(2026, 11, 11)},
        )


def test_first_upgrade_on_a_live_like_database_keeps_every_row(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    _make_live_like(engine)
    rows = upgrade_durable_tables(engine)
    assert rows == {"medicine_requests": (4, 4), "data_reports": (1, 1), **NEW_DOCTOR_TABLES}
    with engine.connect() as conn:
        queries = conn.execute(text("SELECT query FROM medicine_requests ORDER BY id")).scalars()
        assert list(queries) == ["Fexo", "Fexo", "Qwzxyfexo", "Romycin"]
        report = conn.execute(text("SELECT brand_name, brand_code FROM data_reports")).one()
        assert tuple(report) == ("Seclo", None)  # old rows keep NULL for the new column
    assert _version(engine) == HEAD
    # Running again changes nothing.
    again = upgrade_durable_tables(engine)
    assert again == {"medicine_requests": (4, 4), "data_reports": (1, 1), **EMPTY_DOCTOR_TABLES}
    engine.dispose()


def test_the_import_migrates_then_rebuilds_only_seed_tables(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    _make_live_like(engine)
    result = run_import(get_settings().seed_dir, engine)
    assert result.ok, result.errors
    assert result.durable_rows == {
        "medicine_requests": (4, 4),
        "data_reports": (1, 1),
        **NEW_DOCTOR_TABLES,
    }
    with engine.begin() as conn:  # a doctor signs up between two deploys
        conn.execute(
            text(
                "INSERT INTO doctors (email, password_hash, display_name, degrees, specialty,"
                " bmdc_number, status, is_demo, created_at)"
                " VALUES ('a@b.cd', 'x', 'Dr. A', 'MBBS', 'Medicine', 'A-1', 'pending', 0,"
                " '2026-11-13 10:00:00')"
            )
        )
    again = run_import(get_settings().seed_dir, engine)
    assert again.durable_rows["doctors"] == (1, 1)  # the import never drops doctor accounts
    assert again.durable_rows["medicine_requests"] == (4, 4)
    engine.dispose()


def test_0003_on_a_database_at_0002_keeps_every_row(tmp_path: Path) -> None:
    """The live database after R1 (at 0002, with rows): 0003 only adds the doctor tables."""
    from alembic import command
    from alembic.config import Config

    from app.core.config import BACKEND_DIR

    engine = _engine(tmp_path)
    _make_live_like(engine)
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "0002")
    assert _version(engine) == "0002" and not inspect(engine).has_table("doctors")
    rows = upgrade_durable_tables(engine)
    assert rows == {"medicine_requests": (4, 4), "data_reports": (1, 1), **NEW_DOCTOR_TABLES}
    assert _version(engine) == HEAD
    engine.dispose()


def test_a_dry_run_never_migrates(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    result = run_import(get_settings().seed_dir, None, dry_run=True)
    assert result.ok and result.durable_rows == {}
    assert not inspect(engine).has_table("alembic_version")
    engine.dispose()


def test_0004_on_a_database_at_0003_keeps_doctors(tmp_path: Path) -> None:
    """The live database after R2-R4 (at 0003, with a doctor): 0004 adds templates, favourites."""
    from alembic import command
    from alembic.config import Config

    from app.core.config import BACKEND_DIR

    engine = _engine(tmp_path)
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "0003")
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO doctors (email, password_hash, display_name, degrees, specialty,"
                " bmdc_number, status, is_demo, created_at)"
                " VALUES ('a@b.cd', 'x', 'Dr. A', 'MBBS', 'Medicine', 'A-1', 'pending', 0,"
                " '2026-11-13 10:00:00')"
            )
        )
    rows = upgrade_durable_tables(engine)
    assert rows["doctors"] == (1, 1) and rows["doctor_templates"] == (None, 0)
    assert "favourite_tests" in {c["name"] for c in inspect(engine).get_columns("doctors")}
    assert _version(engine) == HEAD
    engine.dispose()
