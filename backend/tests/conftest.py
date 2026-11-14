import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.catalog_cache import catalog_cache
from app.core.config import get_settings
from app.core.db import get_db, make_engine
from app.main import app
from scripts.import_data import run_import


@pytest.fixture(scope="session")
def seeded_engine(tmp_path_factory: pytest.TempPathFactory) -> Engine:
    """A database loaded with the shipped seed data (read-only for tests).

    SQLite by default; set TEST_DATABASE_URL to run the API tests against Postgres.
    Its data is replaced, so never point it at a real database.
    """
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        db_path: Path = tmp_path_factory.mktemp("db") / "seeded.db"
        url = f"sqlite:///{db_path.as_posix()}"
    engine = make_engine(url)
    result = run_import(get_settings().seed_dir, engine)
    assert result.ok, result.errors
    return engine


@pytest.fixture(scope="session")
def client(seeded_engine: Engine) -> Iterator[TestClient]:
    make_session = sessionmaker(bind=seeded_engine, autoflush=False)

    def override_get_db() -> Iterator[Session]:
        with make_session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def clear_catalog_cache() -> None:
    """Tests use different databases; never answer from another test's catalog."""
    catalog_cache.clear()


@pytest.fixture(autouse=True)
def no_real_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests must never call the real OpenAI API, even if backend/.env has a key."""
    monkeypatch.setattr(get_settings(), "openai_api_key", "")


@pytest.fixture(autouse=True)
def reset_rate_limits() -> None:
    """Rate limiters are module-level; start every test with a clean slate."""
    from app.api import (
        brands,
        data_reports,
        interactions,
        medicine_requests,
        pharmacies,
        prescription,
        search,
        stats,
        symptom_guide,
    )

    prescription.per_client_limiter.reset()
    prescription.global_limiter.reset()
    search.search_limiter.reset()
    interactions.interactions_limiter.reset()
    medicine_requests.per_client_limiter.reset()
    medicine_requests.global_limiter.reset()
    stats.stats_limiter.reset()
    pharmacies.pharmacies_limiter.reset()
    symptom_guide.per_client_limiter.reset()
    symptom_guide.global_limiter.reset()
    symptom_guide.setup_limiter.reset()
    data_reports.per_client_limiter.reset()
    data_reports.global_limiter.reset()
    brands.index_limiter.reset()

    from app.api import doctor
    from app.services import doctor_auth

    doctor.signup_limiter.reset()
    doctor.rx_sign_limiter.reset()
    from app.api import rx

    rx.verify_limiter.reset()
    doctor_auth.email_guard.reset()
    doctor_auth.client_guard.reset()
