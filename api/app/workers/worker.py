"""ARQ worker (Section 6: "Redis + ARQ for background jobs, follow-up
timers, and sequence steps. All jobs idempotent with dedupe keys.")

Phase 0 only proves the wiring: a Beanie-connected worker with one
idempotent sample task. Follow-up timers, sequence steps, and lead
scoring jobs land as their owning features do (Phase 1+).
"""

from __future__ import annotations

from typing import Any

from arq import cron
from arq.connections import RedisSettings
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import get_settings
from app.models import DOCUMENT_MODELS
from app.services import audit_service


async def startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    client: AsyncIOMotorClient = AsyncIOMotorClient(settings.mongodb_uri)
    await init_beanie(database=client[settings.mongodb_db_name], document_models=DOCUMENT_MODELS)
    ctx["mongo_client"] = client


async def shutdown(ctx: dict[str, Any]) -> None:
    client = ctx.get("mongo_client")
    if client is not None:
        client.close()


async def ping(ctx: dict[str, Any], *, workspace_id: str, dedupe_key: str) -> str:
    """Sample idempotent job: writes one audit log entry per dedupe_key,
    proving the worker->Mongo path without touching real business data."""
    await audit_service.log_event(
        workspace_id=workspace_id,
        actor="system:worker",
        action="worker.ping",
        target=dedupe_key,
    )
    return "ok"


async def _heartbeat(ctx: dict[str, Any]) -> None:
    pass


class WorkerSettings:
    functions = [ping]
    cron_jobs = [cron(_heartbeat, minute=set(range(0, 60, 15)))]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
