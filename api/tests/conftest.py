import pytest_asyncio
from beanie import init_beanie
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

from app.main import create_app
from app.models import DOCUMENT_MODELS


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
