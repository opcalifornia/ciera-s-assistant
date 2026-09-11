"""Idempotent local demo data (Section 15 Phase 0: "seed script with a
fake demo workspace"). Safe to re-run — upserts by email/name rather
than inserting duplicates.

Usage: `make seed` (runs this against the local docker-compose Mongo).
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))

from beanie import init_beanie  # noqa: E402
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.models import DOCUMENT_MODELS  # noqa: E402
from app.models.brand import AvailabilityRules, Bios, BusinessTerms  # noqa: E402
from app.models.brand import Brand  # noqa: E402
from app.models.user import Role, User  # noqa: E402
from app.models.workspace import Workspace  # noqa: E402

DEMO_EMAIL = "demo-founder@greenroom.local"
DEMO_PASSWORD = "demo-password-change-me"
DEMO_WORKSPACE_NAME = "Demo Talent Co."
DEMO_BRAND_NAME = "Jordan Rivers"


async def seed() -> None:
    mongodb_uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
    db_name = os.environ.get("MONGODB_DB_NAME", "greenroom")

    client = AsyncIOMotorClient(mongodb_uri)
    await init_beanie(database=client[db_name], document_models=DOCUMENT_MODELS)

    workspace = await Workspace.find_one(Workspace.name == DEMO_WORKSPACE_NAME)
    if workspace is None:
        workspace = Workspace(name=DEMO_WORKSPACE_NAME)
        await workspace.insert()
        print(f"Created workspace: {workspace.name} ({workspace.id})")
    else:
        print(f"Workspace already exists: {workspace.name} ({workspace.id})")

    user = await User.find_one(User.email == DEMO_EMAIL)
    if user is None:
        user = User(
            workspace_id=str(workspace.id),
            email=DEMO_EMAIL,
            hashed_password=hash_password(DEMO_PASSWORD),
            full_name="Demo Founder",
            role=Role.OWNER,
        )
        await user.insert()
        print(f"Created user: {user.email} (password: {DEMO_PASSWORD})")
    else:
        print(f"User already exists: {user.email}")

    brand = await Brand.find_one(
        Brand.workspace_id == str(workspace.id), Brand.persona_name == DEMO_BRAND_NAME
    )
    if brand is None:
        brand = Brand(
            workspace_id=str(workspace.id),
            persona_name=DEMO_BRAND_NAME,
            assistant_name="Nova",
            signature="— Nova, AI booking assistant for Jordan Rivers",
            bios=Bios(
                short_25_words="Jordan Rivers is an entertainer, creator, and speaker known for "
                "youth-focused storytelling across stage, screen, and social.",
            ),
            values=["youth impact", "creative education"],
            no_go_categories=["gambling", "alcohol", "political campaigns"],
            availability=AvailabilityRules(
                home_base="Northern California",
                max_travel_days_per_month=6,
                minimum_notice_days=21,
            ),
            business_terms=BusinessTerms(
                deposit_percent=50,
                max_payment_terms_days=30,
                cancellation_policy="Deposit non-refundable inside 14 days of the event.",
                travel_policy="Organizer covers travel + lodging beyond 60 miles of home base.",
            ),
        )
        await brand.insert()
        print(f"Created brand: {brand.persona_name} ({brand.id})")
    else:
        print(f"Brand already exists: {brand.persona_name} ({brand.id})")

    client.close()
    print("\nSeed complete. Log in with:")
    print(f"  email:    {DEMO_EMAIL}")
    print(f"  password: {DEMO_PASSWORD}")


if __name__ == "__main__":
    asyncio.run(seed())
