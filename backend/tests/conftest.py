from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.db import get_db, make_engine
from app.main import app
from scripts.import_data import run_import


@pytest.fixture(scope="session")
def seeded_engine(tmp_path_factory: pytest.TempPathFactory) -> Engine:
    """A SQLite database loaded with the shipped seed data (read-only for tests)."""
    db_path: Path = tmp_path_factory.mktemp("db") / "seeded.db"
    engine = make_engine(f"sqlite:///{db_path.as_posix()}")
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
def no_real_gemini(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests must never call the real Gemini API, even if backend/.env has a key."""
    monkeypatch.setattr(get_settings(), "gemini_api_key", "")
