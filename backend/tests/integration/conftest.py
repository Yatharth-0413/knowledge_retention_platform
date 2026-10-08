"""Integration test fixtures: a real, disposable Postgres+pgvector database (a
separate `knowledge_retention_test` database on the same server docker-compose
already runs - never the dev database) plus a FastAPI TestClient wired to it.

Ollama and the embedding model are monkeypatched out so these tests are fast and
hermetic (no live Ollama server, no sentence-transformers model load) while still
exercising the real ORM, routers, and Postgres/pgvector constraints end to end -
this is exactly the layer where this session's cross-team leak bugs and the P0
attribution bug lived, so these tests hit real SQL, not mocks.

Run with: docker compose exec backend pytest tests/integration
(needs the `postgres` service reachable at the hostname below - true inside the
compose network, which is where these are meant to run.)
"""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

_ADMIN_DATABASE_URL = os.environ.get(
    "TEST_ADMIN_DATABASE_URL", "postgresql+psycopg://postgres:postgres@postgres:5432/postgres"
)
_TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://postgres:postgres@postgres:5432/knowledge_retention_test"
)
_TEST_DB_NAME = _TEST_DATABASE_URL.rsplit("/", 1)[-1]


def _ensure_test_database_exists() -> None:
    admin_engine = create_engine(_ADMIN_DATABASE_URL, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": _TEST_DB_NAME}
            ).first()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{_TEST_DB_NAME}"'))
    finally:
        admin_engine.dispose()


@pytest.fixture(scope="session")
def test_engine():
    import app.main  # noqa: F401 - imports every router/model so Base.metadata (and the
    # declarative registry's relationship-string resolution, e.g. relationship("User")) is
    # fully populated before create_all/queries run - see PROGRESS.md's note on this gotcha.
    from app.database import Base

    _ensure_test_database_exists()
    engine = create_engine(_TEST_DATABASE_URL)
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()

    # Tables are created once per test session, not per test: users<->teams is a
    # deliberate two-way FK (a user has a team_id, a team has a manager_id back
    # into users), which create_all tolerates but Base.metadata.drop_all cannot -
    # it raises CircularDependencyError trying to topologically sort the cycle.
    # So tests reset data with TRUNCATE ... CASCADE (see db_session below) instead
    # of drop_all/create_all per test.
    Base.metadata.create_all(engine)
    table_names = ", ".join(f'"{name}"' for name in Base.metadata.tables)
    with engine.connect() as conn:
        # Guard against stale rows left over from a previous test run that was
        # interrupted before its own per-test truncate ran (e.g. this database
        # already existed with data from an earlier pytest invocation).
        conn.execute(text(f"TRUNCATE {table_names} RESTART IDENTITY CASCADE"))
        conn.commit()
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(test_engine):
    from app.database import Base

    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        table_names = ", ".join(f'"{name}"' for name in Base.metadata.tables)
        with test_engine.connect() as conn:
            # CASCADE handles FK dependency order itself - no topological sort needed,
            # unlike drop_all/create_all.
            conn.execute(text(f"TRUNCATE {table_names} RESTART IDENTITY CASCADE"))
            conn.commit()


@pytest.fixture
def client(db_session, tmp_path, monkeypatch):
    from app.config import settings
    from app.database import get_db
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db_session
    # Real files written to a throwaway tmp dir, never the real uploads/ folder.
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))

    # Hermetic & fast: no real Ollama server, no sentence-transformers model load.
    monkeypatch.setattr("app.knowledge.topic_extraction.ollama_generate", lambda *a, **k: None)
    monkeypatch.setattr("app.chat.service.ollama_generate", lambda *a, **k: None)
    monkeypatch.setattr("app.knowledge.service.embed_query", lambda text: [0.01] * 384)
    monkeypatch.setattr("app.knowledge.service.embed_texts", lambda texts: [[0.01] * 384 for _ in texts])
    monkeypatch.setattr("app.chat.service.embed_query", lambda text: [0.01] * 384)

    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    from app.auth.security import create_access_token

    def _headers(user) -> dict[str, str]:
        token = create_access_token(subject=str(user.id), extra_claims={"role": user.role.value})
        return {"Authorization": f"Bearer {token}"}

    return _headers
