"""Real token, upload, lease, correction and tenant boundaries against disposable PostgreSQL."""

import asyncio
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, cast
from uuid import UUID

import pytest
from sqlalchemy.exc import IntegrityError
from test_delivery_integration import DeliveryFacts
from test_delivery_integration import auth as auth_fixture
from test_delivery_integration import delivery as delivery_fixture
from test_delivery_integration import facts as facts_fixture

from forge.domain.tests import MAX_REPORT_BYTES
from forge.integrations.github import GitHubApp
from forge.integrations.junit import parse_junit
from forge.repositories.pipeline import LostLease
from forge.security.identity import now, token_hash
from forge.workers.github import GitHubWorker

auth = auth_fixture
facts = facts_fixture
delivery = delivery_fixture
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("FORGE_RUN_DB_TESTS") != "1", reason="Dedicated test database required"
    ),
]
XML = b"""<testsuites tests="3"><testsuite name="suite" tests="3">
<testcase classname="module" name="pass" time="1"/>
<testcase classname="module" name="retry" time="2">
<flakyFailure message="original failure" time=".5"/></testcase>
<testcase classname="module" name="skip"><skipped/></testcase>
</testsuite></testsuites>"""
CORRECTION = (
    b'<testsuite name="suite"><testcase classname="module" name="pass" time="2">'
    b'<failure message="corrected failure"/></testcase></testsuite>'
)


@dataclass
class UploadFacts(DeliveryFacts):
    credential: str = field(default="", repr=False)
    token_id: UUID | None = None
    provider_run: int = 321

    @property
    def repository_path(self) -> str:
        return f"/organizations/{self.organization}/repositories/{self.repository}"

    @property
    def storage(self):
        return self.auth.app.state.test_service.repository

    async def upload(self, payload: bytes = XML, **query: Any):
        return await self.owner.client.post(
            "/api/v1" + self.repository_path + "/test-reports",
            params={
                "workflow_run_id": self.provider_run,
                "run_attempt": 1,
                "report_key": "unit",
                **query,
            },
            headers={
                "Authorization": f"Bearer {self.credential}",
                "Content-Type": "application/xml",
            },
            content=payload,
        )

    async def rows(self, table: str, columns: str = "*"):
        async with self.storage.transaction() as connection:
            await self.storage.tenant(connection, self.organization)
            return await self.storage.many(
                connection,
                f"SELECT {columns} FROM forge.{table} WHERE organization_id=:org",
                org=self.organization,
            )

    async def process(self):
        # Dispatching report jobs must not call a GitHub provider at all.
        worker = GitHubWorker(
            self.storage,
            cast(GitHubApp, object()),
            test_secret=self.auth.settings.auth_secret.get_secret_value(),
        )
        assert await worker.run_once()


@pytest.fixture
async def upload(delivery: DeliveryFacts) -> AsyncIterator[UploadFacts]:
    item = UploadFacts(**vars(delivery))
    await item.update("integrations", item.integration, status="active")
    await item.update("repositories", item.repository, is_demo=False, authorized=True)
    await item.run(provider_run_id=item.provider_run)
    response = await item.auth.mutate(
        item.owner.client, "POST", item.repository_path + "/service-tokens", {"name": "CI fixture"}
    )
    assert response.status_code == 201, response.text
    item.credential = response.json()["credential"]
    item.token_id = UUID(response.json()["token"]["id"])
    try:
        yield item
    finally:
        # The dispatcher is global, but each simulated app has its own encryption key.
        # Do not leave this fixture's deliberately pending jobs for a later app instance.
        async with item.storage.transaction() as connection:
            await item.storage.tenant(connection, item.organization)
            await item.storage.cancel_repository(connection, item.organization, item.repository)
        await item.storage.clear_payloads()


async def test_upload_encrypted_then_atomically_stores_explicit_retry_and_clears_xml(
    upload: UploadFacts,
):
    response = await upload.upload()
    assert response.status_code == 202, response.text
    report = (await upload.rows("test_reports"))[0]
    assert report["status"] == "queued" and b"testcase" not in bytes(report["payload"])
    assert upload.auth.app.state.test_service.cipher.decrypt(bytes(report["payload"])) == XML
    await upload.process()
    report = (await upload.rows("test_reports"))[0]
    assert report["status"] == "completed" and report["payload"] is None
    assert (
        report["case_count"],
        report["execution_count"],
        report["passed_count"],
        report["skipped_count"],
    ) == (3, 4, 2, 1)
    executions = await upload.rows("test_executions")
    assert len(executions) == 4 and sum(row["is_final"] for row in executions) == 3
    retries = sorted(
        [row for row in executions if row["failure_message"] or row["retry_ordinal"]],
        key=lambda row: row["retry_ordinal"],
    )
    assert [(row["outcome"], row["retry_ordinal"], row["is_final"]) for row in retries] == [
        ("failed", 0, False),
        ("passed", 1, True),
    ]
    assert retries[0]["failure_message"] == "original failure"
    assert retries[0]["test_identity_id"] == retries[1]["test_identity_id"]
    assert len(await upload.rows("test_identities")) == 3
    assert len(await upload.rows("test_suites")) == 1
    assert (await upload.rows("jobs"))[0]["state"] == "succeeded"


async def test_replay_race_and_correction_replaces_only_after_success(upload: UploadFacts):
    first, second = await asyncio.gather(upload.upload(), upload.upload())
    assert first.status_code == second.status_code == 202
    assert first.json()["id"] == second.json()["id"]
    assert {first.json()["duplicate"], second.json()["duplicate"]} == {False, True}
    original = first.json()["id"]
    await upload.process()
    assert (await upload.upload(CORRECTION)).status_code == 409
    invalid = await upload.upload(b"<testsuite>", supersedes=original)
    assert invalid.status_code == 202
    await upload.process()
    rows = await upload.rows("test_reports")
    assert next(row for row in rows if str(row["id"]) == original)["superseded_by_id"] is None
    assert (
        next(row for row in rows if str(row["id"]) == invalid.json()["id"])["error_code"]
        == "malformed_xml"
    )
    replacement = await upload.upload(CORRECTION, supersedes=original)
    assert replacement.status_code == 202, replacement.text
    assert (await upload.upload(XML)).json()["id"] == original
    await upload.process()
    rows = await upload.rows("test_reports")
    assert next(row for row in rows if str(row["id"]) == original)["superseded_by_id"] == UUID(
        replacement.json()["id"]
    )
    assert (await upload.upload(CORRECTION)).json()["duplicate"] is True
    assert len(await upload.rows("jobs")) == 3


async def test_machine_auth_is_separate_and_precedes_body_consumption(upload: UploadFacts):
    async def unread_body():
        raise AssertionError("Unauthorized body must not be consumed")
        yield b""  # pragma: no cover

    path = "/api/v1" + upload.repository_path + "/test-reports"
    query = {"workflow_run_id": 321, "run_attempt": 1, "report_key": "unit"}
    response = await upload.owner.client.post(
        path, params=query, headers={"Content-Type": "application/xml"}, content=unread_body()
    )
    assert response.status_code == 401
    human = upload.owner.client.cookies.get("forge_access")
    response = await upload.owner.client.post(
        path,
        params=query,
        headers={"Authorization": f"Bearer {human}", "Content-Type": "application/xml"},
        content=XML,
    )
    assert response.status_code == 401
    outsider = await upload.auth.register()
    organization = await upload.auth.organization(outsider)
    response = await outsider.client.post(
        f"/api/v1/organizations/{organization}/repositories/{upload.repository}/test-reports",
        params=query,
        headers={"Authorization": f"Bearer {upload.credential}", "Content-Type": "application/xml"},
        content=XML,
    )
    assert response.status_code == 401 and not await upload.rows("test_reports")
    machine = await upload.auth.client()
    assert (
        await machine.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {upload.credential}"}
        )
    ).status_code == 401


async def test_stream_limit_content_type_parent_and_metadata_checks(upload: UploadFacts):
    too_large = await upload.upload(b" " * (MAX_REPORT_BYTES + 1))
    assert too_large.status_code == 413
    assert (await upload.upload(workflow_run_id=999)).status_code == 422
    assert (await upload.upload(commit_sha="b" * 40)).status_code == 409
    path = "/api/v1" + upload.repository_path + "/test-reports"
    for headers in (
        {"Content-Type": "application/zip"},
        {"Content-Type": "application/xml", "Content-Encoding": "gzip"},
    ):
        response = await upload.owner.client.post(
            path,
            params={"workflow_run_id": 321, "run_attempt": 1, "report_key": "unit"},
            headers={"Authorization": f"Bearer {upload.credential}", **headers},
            content=XML,
        )
        assert response.status_code == 415
    assert not await upload.rows("test_reports")
    assert (await upload.upload()).status_code == 202
    assert (await upload.upload(environment="different")).status_code == 409


async def test_token_hash_only_verified_manager_csrf_list_and_revocation(upload: UploadFacts):
    token = (await upload.rows("service_tokens"))[0]
    assert token["token_hash"] == token_hash(upload.credential)
    response = await upload.owner.client.get("/api/v1" + upload.repository_path + "/service-tokens")
    assert response.status_code == 200
    assert upload.credential not in response.text and "token_hash" not in response.text
    viewer = await upload.auth.register()
    await upload.auth.join(upload.owner, str(upload.organization), viewer, "viewer")
    assert (
        await upload.auth.mutate(
            viewer.client, "POST", upload.repository_path + "/service-tokens", {"name": "forbidden"}
        )
    ).status_code == 403
    assert (
        await upload.owner.client.post(
            "/api/v1" + upload.repository_path + "/service-tokens", json={"name": "no csrf"}
        )
    ).status_code == 403
    await upload.upload()
    response = await upload.auth.mutate(
        upload.owner.client,
        "DELETE",
        f"/organizations/{upload.organization}/service-tokens/{upload.token_id}",
    )
    assert response.status_code == 204
    report = (await upload.rows("test_reports"))[0]
    assert report["payload"] is None and report["error_code"] == "token_revoked"
    assert (await upload.upload()).status_code == 401


async def test_token_revocation_fences_pending_processing(upload: UploadFacts):
    await upload.upload()
    lease = await upload.storage.claim()
    assert lease
    assert lease.organization_id == upload.organization
    async with upload.storage.transaction() as connection:
        await upload.storage.tenant(connection, upload.organization)
        _, report = await upload.storage.report_work(connection, lease)
    parsed = parse_junit(XML)
    await upload.auth.mutate(
        upload.owner.client,
        "DELETE",
        f"/organizations/{upload.organization}/service-tokens/{upload.token_id}",
    )
    with pytest.raises(LostLease):
        async with upload.storage.transaction() as connection:
            await upload.storage.tenant(connection, upload.organization)
            await upload.storage.report_work(connection, lease)
            await upload.storage.persist_report(connection, report, parsed)
    assert not await upload.rows("test_executions")


async def test_expired_raw_payload_cleanup_is_bounded_and_not_readable_cross_tenant(
    upload: UploadFacts,
):
    await upload.upload()
    report = (await upload.rows("test_reports"))[0]
    await upload.update(
        "test_reports", report["id"], payload_expires_at=now() - timedelta(seconds=1)
    )
    async with upload.storage.transaction() as connection:
        assert await upload.storage.many(connection, "SELECT id FROM forge.test_reports") == []
    await upload.storage.clear_payloads()
    report = (await upload.rows("test_reports"))[0]
    assert report["status"] == "failed" and report["error_code"] == "payload_expired"
    assert report["payload"] is None
    assert (await upload.rows("jobs"))[0]["state"] == "canceled"


async def test_test_policy_partial_updates_version_validation_and_audit(upload: UploadFacts):
    path = upload.repository_path + "/test-policy"
    original = await upload.owner.client.get("/api/v1" + path)
    assert original.json()["version"] == 1 and original.json()["window_days"] == 14
    first = await upload.auth.mutate(upload.owner.client, "PATCH", path, {"min_executions": 12})
    assert first.status_code == 200 and first.json()["min_executions"] == 12
    assert first.json()["version"] == 2
    next_policy = await upload.auth.mutate(
        upload.owner.client, "PATCH", path, {"excluded_branches": ["archive"]}
    )
    assert next_policy.json()["version"] == 3 and next_policy.json()["min_executions"] == 12
    for changes in (
        {},
        {"window_days": None},
        {"failure_rate_low": 0.99},
        {"min_transitions": False},
    ):
        assert (
            await upload.auth.mutate(upload.owner.client, "PATCH", path, changes)
        ).status_code == 422
    audits = await upload.rows("audit_events")
    assert sum(row["action"] == "test_policy.updated" for row in audits) == 2


async def test_suites_and_executions_require_same_report_and_repository(upload: UploadFacts):
    await upload.upload()
    await upload.process()
    first_report = (await upload.rows("test_reports"))[0]
    suite = (await upload.rows("test_suites"))[0]
    identity = (await upload.rows("test_identities"))[0]
    other = await upload.repo()
    with pytest.raises(IntegrityError):
        await upload.insert(
            "test_executions",
            {
                "repository_id": other,
                "report_id": first_report["id"],
                "suite_id": suite["id"],
                "test_identity_id": identity["id"],
                "ordinal": 90,
                "source_ordinal": 90,
                "retry_ordinal": 0,
                "is_final": True,
                "outcome": "passed",
            },
        )
    await upload.upload(CORRECTION, report_key="other-report")
    await upload.process()
    other_report = next(
        row for row in await upload.rows("test_reports") if row["report_key"] == "other-report"
    )
    with pytest.raises(IntegrityError):
        await upload.insert(
            "test_executions",
            {
                "repository_id": upload.repository,
                "report_id": other_report["id"],
                "suite_id": suite["id"],
                "test_identity_id": identity["id"],
                "ordinal": 90,
                "source_ordinal": 90,
                "retry_ordinal": 0,
                "is_final": True,
                "outcome": "passed",
            },
        )
