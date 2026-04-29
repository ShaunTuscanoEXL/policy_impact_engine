"""Test fixtures.

Provides a self-contained SQLite-backed test app so integration tests
can run without a Postgres dependency. Production code is unchanged;
the swap is done by overriding the FastAPI ``get_db`` dependency on
the test app instance.
"""
from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Ensure every model module is imported so Base.metadata is fully populated
# *before* we import the FastAPI app instance (otherwise the lazy lifespan
# import order matters and create_all may miss tables).
import app.models  # noqa: F401  — registers BRD/Rule/TestCase/Loan/LiveRepo/Merge

from app.database import Base, get_db
from app.main import app as fastapi_app  # alias to avoid shadowing the `app` package


# ── Async backend selector ───────────────────────────────────────────────

@pytest.fixture
def anyio_backend():
    return "asyncio"


# ── In-memory SQLite engine, per-test isolation ──────────────────────────

@pytest_asyncio.fixture
async def db_engine():
    """Fresh on-disk SQLite database per test (file gets deleted after).

    On-disk (rather than ``:memory:``) so that the async engine and the
    session see the same connection pool consistently. The file is
    namespaced by uuid to keep parallel tests isolated.
    """
    db_path = os.path.abspath(f"./_test_{uuid.uuid4().hex}.sqlite")
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        await engine.dispose()
        try:
            os.remove(db_path)
        except OSError:
            pass


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncIterator[AsyncSession]:
    """A bare AsyncSession for service-level tests."""
    Session = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        yield session


# ── HTTP client wired to the test database ───────────────────────────────

@pytest_asyncio.fixture
async def client(db_engine) -> AsyncIterator[AsyncClient]:
    """FastAPI TestClient with the database dependency swapped to SQLite."""
    Session = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def _override_get_db():
        async with Session() as session:
            yield session

    fastapi_app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=fastapi_app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        fastapi_app.dependency_overrides.pop(get_db, None)
