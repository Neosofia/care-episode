from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models.care_episode import CareEpisode
from src.models.risk import InteractionRiskState


def _normalize_to_psycopg_sqlalchemy_url(url: str) -> str:
    if url.startswith("postgresql+psycopg2://"):
        return url.replace("postgresql+psycopg2://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


@pytest.fixture(scope="module")
def roster_postgres_session_factory():
    """Real Postgres session factory for roster integration tests (Docker required)."""
    pytest.importorskip("testcontainers")
    from testcontainers.postgres import PostgresContainer

    try:
        container = PostgresContainer("postgres:18")
        container.start()
    except Exception as exc:
        pytest.skip(f"Postgres testcontainer unavailable: {exc}")

    try:
        db_url = _normalize_to_psycopg_sqlalchemy_url(container.get_connection_url())
        engine = create_engine(db_url, echo=False)
        CareEpisode.__table__.create(bind=engine, checkfirst=True)
        InteractionRiskState.__table__.create(bind=engine, checkfirst=True)
        factory = sessionmaker(bind=engine, expire_on_commit=False)
        yield factory
    finally:
        container.stop()
