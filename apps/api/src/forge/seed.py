"""Opt-in local demo identities. Prints generated credentials only at initial creation."""

import asyncio
import os
import secrets
from uuid import uuid4

from forge.config import Settings
from forge.domain.identity import Actor
from forge.repositories.database import create_database_engine
from forge.repositories.identity import IdentityRepository
from forge.security.identity import PASSWORDS
from forge.services.identity import IdentityService
from forge.services.organizations import OrganizationService


async def seed() -> None:
    settings = Settings()
    if settings.environment == "production":
        raise SystemExit("Demo seeding is disabled in production.")
    supplied = os.environ.get("FORGE_DEMO_PASSWORD")
    if supplied is not None and not 12 <= len(supplied) <= 128:
        raise SystemExit("FORGE_DEMO_PASSWORD must contain 12 to 128 characters.")
    engine = create_database_engine(settings)
    repository = IdentityRepository(engine)
    organizations = OrganizationService(IdentityService(repository, settings))
    try:
        for number, name in ((1, "Demo One"), (2, "Demo Two")):
            email = f"owner-{number}@forge-demo.example.com"
            password = supplied or secrets.token_urlsafe(24)
            created = False
            async with repository.transaction() as connection:
                user = await repository.user_by_email(connection, email)
                if user is None:
                    identifier = uuid4()
                    await repository.create_user(
                        connection, identifier, name, email, PASSWORDS.hash(password), verified=True
                    )
                    created = True
                else:
                    identifier = user["id"]
            actor = Actor(identifier, uuid4(), name, email, True, "")
            existing = await organizations.list(actor, 100, None)
            slug = f"forge-demo-{number}"
            match = next((item for item in existing["data"] if item["slug"] == slug), None)
            if match is None:
                await organizations.create(actor, name, slug, demo=True)
            elif not match["is_demo"]:
                raise SystemExit("A demo URL is already used by a non-demo organization.")
            if created:
                print(f"Created synthetic demo identity: {email}\nPassword: {password}")
            else:
                print(f"Demo identity already exists: {email}; password unchanged.")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
