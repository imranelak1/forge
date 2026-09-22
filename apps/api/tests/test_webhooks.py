"""Real ingress/tenant tests with no external GitHub requests."""

import hashlib
import hmac
import json
import os
import secrets
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from test_auth import AuthHarness
from test_auth import auth as auth_fixture

auth = auth_fixture

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("FORGE_RUN_DB_TESTS") != "1", reason="Dedicated test DB required"),
]
WEBHOOK_SECRET = "local-webhook-fixture-secret-with-32-bytes"


@dataclass
class Source:
    organization: UUID
    integration: UUID
    repository: UUID
    installation: int
    provider_repository: int


async def source(harness: AuthHarness) -> Source:
    owner = await harness.register()
    await harness.verify(owner)
    organization = UUID(await harness.organization(owner))
    result = Source(
        organization, uuid4(), uuid4(), secrets.randbelow(2**50) + 1, secrets.randbelow(2**50) + 1
    )
    repository = harness.app.state.identity_service.repository
    async with repository.transaction() as connection:
        await repository.tenant(connection, organization)
        await repository.execute(
            connection,
            "INSERT INTO forge.integrations "
            "(organization_id,id,installation_id,account_login,account_type) "
            "VALUES (:org,:id,:installation,'fixture','Organization')",
            org=organization,
            id=result.integration,
            installation=result.installation,
        )
        await repository.execute(
            connection,
            "INSERT INTO forge.github_installation_bindings VALUES (:installation,:org,:id)",
            org=organization,
            id=result.integration,
            installation=result.installation,
        )
        await repository.execute(
            connection,
            "INSERT INTO forge.repositories "
            "(organization_id,id,integration_id,provider_id,owner,name,"
            "full_name,html_url,default_branch,is_private,archived,selected) VALUES "
            "(:org,:id,:integration,:provider,'fixture','repo','fixture/repo',"
            "'https://github.com/fixture/repo','main',true,false,true)",
            org=organization,
            id=result.repository,
            integration=result.integration,
            provider=result.provider_repository,
        )
    harness.settings.github_app_webhook_secret = SecretStr(WEBHOOK_SECRET)
    return result


def payload(item: Source) -> dict[str, Any]:
    return {
        "installation": {"id": item.installation},
        "repository": {"id": item.provider_repository},
        "action": "opened",
        "number": 42,
    }


async def send(
    client: httpx.AsyncClient,
    data: dict[str, Any] | bytes,
    *,
    event: str = "pull_request",
    delivery: UUID | None = None,
    signature: str | None = None,
) -> httpx.Response:
    body = data if isinstance(data, bytes) else json.dumps(data).encode()
    digest = hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return await client.post(
        "/api/v1/webhooks/github",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Delivery": str(delivery or uuid4()),
            "X-GitHub-Event": event,
            "X-Hub-Signature-256": signature or f"sha256={digest}",
        },
    )


async def test_signature_is_checked_before_parsing_and_body_is_bounded(auth: AuthHarness) -> None:
    await source(auth)
    client = await auth.client()
    assert (await send(client, b"not json", signature="sha256=" + "0" * 64)).status_code == 401
    assert (await send(client, b"not json")).status_code == 400
    assert (await send(client, b"x" * (1048576 + 1))).status_code == 413
    response = await client.post("/api/v1/webhooks/github", json={})
    assert response.status_code == 400


async def test_receipt_and_job_are_atomic_and_duplicate_is_idempotent(auth: AuthHarness) -> None:
    item = await source(auth)
    client = await auth.client()
    delivery = uuid4()
    first = await send(client, payload(item), delivery=delivery)
    duplicate = await send(client, payload(item), delivery=delivery)
    assert first.status_code == 202 and first.json()["status"] == "queued"
    assert duplicate.status_code == 200 and duplicate.json() == first.json()
    conflict = await send(client, {**payload(item), "number": 43}, delivery=delivery)
    assert conflict.status_code == 409
    assert (await send(client, payload(item), delivery=delivery, event="push")).status_code == 409
    repo = auth.app.state.identity_service.repository
    async with repo.transaction() as connection:
        await repo.tenant(connection, item.organization)
        assert (
            await connection.scalar(
                text("SELECT count(*) FROM forge.jobs WHERE inbox_id=:id"), {"id": delivery}
            )
            == 1
        )
        assert (
            await connection.scalar(
                text("SELECT count(*) FROM forge.webhook_inbox WHERE id=:id"), {"id": delivery}
            )
            == 1
        )


@pytest.mark.parametrize("event,reason", [("check_suite", "unsupported_event"), ("ping", "ping")])
async def test_future_events_are_ignored_without_claiming_processing(
    auth: AuthHarness,
    event: str,
    reason: str,
) -> None:
    item = await source(auth)
    response = await send(await auth.client(), payload(item), event=event)
    assert response.status_code == 202
    assert response.json()["status"] == "ignored" and response.json()["reason"] == reason
    repo = auth.app.state.identity_service.repository
    async with repo.transaction() as connection:
        await repo.tenant(connection, item.organization)
        assert (
            await connection.scalar(
                text("SELECT count(*) FROM forge.jobs WHERE inbox_id=:id"),
                {"id": UUID(response.json()["receipt_id"])},
            )
            == 0
        )


async def test_unknown_installation_and_cross_installation_repository_cannot_ingest(
    auth: AuthHarness,
) -> None:
    one, two = await source(auth), await source(auth)
    client = await auth.client()
    unmapped = await send(client, {**payload(one), "installation": {"id": 2**62}})
    assert unmapped.json()["reason"] == "unbound_installation"
    mismatched = await send(client, {**payload(one), "repository": {"id": two.provider_repository}})
    assert mismatched.json()["reason"] == "repository_not_selected"
    repo = auth.app.state.identity_service.repository
    async with repo.transaction() as connection:
        await repo.tenant(connection, one.organization)
        assert await connection.scalar(text("SELECT count(*) FROM forge.webhook_inbox")) == 0


async def test_suspension_cancels_work_before_acknowledgement(auth: AuthHarness) -> None:
    item = await source(auth)
    service = auth.app.state.webhook_service
    repo = service.repository
    async with repo.transaction() as connection:
        await repo.tenant(connection, item.organization)
        run = await service.pipeline.enqueue_sync(
            connection,
            item.organization,
            item.integration,
            item.repository,
        )
    response = await send(
        await auth.client(),
        {
            "installation": {"id": item.installation},
            "action": "suspend",
        },
        event="installation",
    )
    assert response.status_code == 202 and response.json()["status"] == "processed"
    async with repo.transaction() as connection:
        await repo.tenant(connection, item.organization)
        assert (
            await connection.scalar(
                text("SELECT status FROM forge.integrations WHERE id=:id"), {"id": item.integration}
            )
            == "suspended"
        )
        assert (
            await connection.scalar(
                text("SELECT authorized FROM forge.repositories WHERE id=:id"),
                {"id": item.repository},
            )
            is False
        )
        assert (
            await connection.scalar(
                text("SELECT status FROM forge.sync_runs WHERE id=:id"), {"id": run["id"]}
            )
            == "canceled"
        )
    ignored = await send(await auth.client(), payload(item))
    assert ignored.json()["reason"] == "integration_inactive"


async def test_removed_repository_is_revoked_before_catalog_reconciliation(
    auth: AuthHarness,
) -> None:
    item = await source(auth)
    old_delivery = uuid4()
    assert (
        await send(await auth.client(), payload(item), delivery=old_delivery)
    ).status_code == 202
    repo = auth.app.state.identity_service.repository
    async with repo.transaction() as connection:
        await repo.tenant(connection, item.organization)
        original_version = await connection.scalar(
            text("SELECT updated_at FROM forge.integrations WHERE id=:id"),
            {"id": item.integration},
        )
    response = await send(
        await auth.client(),
        {
            "installation": {"id": item.installation},
            "action": "removed",
            "repositories_removed": [{"id": item.provider_repository}],
        },
        event="installation_repositories",
    )
    assert response.status_code == 202
    async with repo.transaction() as connection:
        await repo.tenant(connection, item.organization)
        row = await repo.one(
            connection,
            "SELECT authorized,selected FROM forge.repositories WHERE id=:id",
            id=item.repository,
        )
        assert row == {"authorized": False, "selected": False}
        assert await connection.scalar(
            text("SELECT updated_at>:version FROM forge.integrations WHERE id=:id"),
            {"id": item.integration, "version": original_version},
        )
        canceled = await repo.one(
            connection,
            "SELECT j.state,j.fence,w.status,w.payload,r.status AS receipt_status "
            "FROM forge.jobs j JOIN forge.webhook_inbox w ON w.id=j.inbox_id "
            "JOIN forge.webhook_receipts r ON r.delivery_id=w.id WHERE w.id=:id",
            id=old_delivery,
        )
        assert canceled == {
            "state": "canceled",
            "fence": 1,
            "status": "ignored",
            "payload": {},
            "receipt_status": "ignored",
        }
    assert (await send(await auth.client(), payload(item))).json()[
        "reason"
    ] == "repository_not_selected"


async def test_pipeline_data_and_composite_relationships_are_tenant_isolated(
    auth: AuthHarness,
) -> None:
    one, two = await source(auth), await source(auth)
    repo = auth.app.state.identity_service.repository
    async with repo.transaction() as connection:
        assert await connection.scalar(text("SELECT count(*) FROM forge.repositories")) == 0
        await repo.tenant(connection, one.organization)
        assert (
            await connection.scalar(
                text("SELECT count(*) FROM forge.repositories WHERE id=:id"), {"id": two.repository}
            )
            == 0
        )
        assert (
            await connection.scalar(
                text("UPDATE forge.repositories SET selected=true WHERE id=:id RETURNING id"),
                {"id": two.repository},
            )
            is None
        )
    with pytest.raises(IntegrityError):
        async with repo.transaction() as connection:
            await repo.tenant(connection, one.organization)
            await repo.execute(
                connection,
                "INSERT INTO forge.commits "
                "(organization_id,id,repository_id,sha,message,committed_at,html_url) "
                "VALUES (:org,:id,:repo,:sha,'cross-tenant',now(),'https://github.com/fixture/repo')",
                org=one.organization,
                id=uuid4(),
                repo=two.repository,
                sha="a" * 40,
            )
    async with repo.transaction() as connection:
        assert await connection.scalar(text("SELECT count(*) FROM forge.repositories")) == 0
