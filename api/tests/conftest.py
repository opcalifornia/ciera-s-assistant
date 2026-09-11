import pytest
import pytest_asyncio
from beanie import init_beanie
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

from app.main import create_app
from app.models import DOCUMENT_MODELS


@pytest.fixture(autouse=True, scope="session")
def _init_beanie_for_document_construction():
    """Beanie Documents need `init_beanie` called once before they can be
    constructed at all (even without saving) — this makes plain unit
    tests that build a `Brand`/`Workspace`/etc. in memory work without
    every test file needing its own ASGI app + mongomock setup. Tests
    that exercise real persistence (e.g. the auth flow) still get their
    own isolated database via `app_client` below."""
    import asyncio

    client = AsyncMongoMockClient()
    asyncio.run(
        init_beanie(database=client["greenroom_test_session"], document_models=DOCUMENT_MODELS)
    )


@pytest_asyncio.fixture
async def app_client():
    """Full ASGI app against an in-memory mongomock database — no real
    Mongo, no Docker, no cost. Bypasses the app's lifespan (which points
    at a real Mongo URI) and initializes Beanie against the mock client
    instead."""
    client = AsyncMongoMockClient()
    await init_beanie(database=client["greenroom_test"], document_models=DOCUMENT_MODELS)

    # httpx's ASGITransport only sends "http" scope traffic, never "lifespan",
    # so the app's real-Mongo lifespan handler below never runs here — Beanie
    # is already initialized against the mock client above.
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
