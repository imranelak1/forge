"""Durable evidence pages against PostgreSQL, with only GitHub I/O faked."""

import os
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from test_auth import auth  # noqa: F401
from test_pipeline_integration import Pipeline, Provider, commit, pipeline, pr  # noqa: F401

from forge.domain import github as normalize
from forge.repositories.pipeline import LostLease, PipelineRepository

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("FORGE_RUN_DB_TESTS") != "1", reason="Dedicated test DB not supplied"
    ),
]


def review(identifier: int, state: str = "APPROVED") -> dict[str, Any]:
    return {
        "id": identifier,
        "user": {"login": "reviewer", "type": "User"},
        "state": state,
        "submitted_at": "2026-01-02T00:00:00Z",
    }


def issue(number: int) -> dict[str, Any]:
    return {
        "id": 8000 + number,
        "number": number,
        "title": "Tracked work",
        "state": "open",
        "user": {"login": "reporter", "type": "User"},
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-03T00:00:00Z",
        "closed_at": None,
        "html_url": f"https://github.com/team/repo-1/issues/{number}",
    }


@dataclass
class EvidenceProvider(Provider):
    issues_allowed: bool = False
    review_pages: dict[int, list[dict[str, Any]]] = field(default_factory=lambda: {1: [review(1)]})
    timelines: dict[int, list[dict[str, Any]]] = field(default_factory=dict)
    members: dict[int, list[dict[str, Any]]] = field(default_factory=lambda: {1: [commit(1)]})
    file_pages: dict[int, list[dict[str, Any]]] = field(
        default_factory=lambda: {
            1: [
                {
                    "filename": "src/main.py",
                    "status": "modified",
                    "additions": 4,
                    "deletions": 2,
                    "changes": 6,
                }
            ]
        }
    )
    issue_pages: dict[int, list[dict[str, Any]]] = field(default_factory=dict)

    async def enrichment_credentials(self, identifier: int) -> tuple[str, bool]:
        return await self.installation_token(identifier), self.issues_allowed

    async def cicd_credentials(self, identifier: int) -> tuple[str, frozenset[str]]:
        return await self.installation_token(identifier), frozenset()

    async def reviews(
        self, token: str, owner: str, name: str, number: int, page: int
    ) -> list[dict[str, Any]]:
        self.calls.append(("reviews", page))
        return self.review_pages.get(page, [])

    async def timeline(
        self, token: str, owner: str, name: str, number: int, page: int
    ) -> list[dict[str, Any]]:
        self.calls.append(("timeline", page))
        return self.timelines.get(number, []) if page == 1 else []

    async def pull_request_commits(
        self, token: str, owner: str, name: str, number: int, page: int
    ) -> list[dict[str, Any]]:
        return self.members.get(page, [])

    async def commit_details(
        self, token: str, owner: str, name: str, identifier: str, page: int
    ) -> dict[str, Any]:
        self.calls.append(("files", page))
        return {
            **commit(int(identifier, 16)),
            "stats": {"additions": 4, "deletions": 2, "total": 6},
            "files": self.file_pages.get(page, []),
        }

    async def issues(
        self, token: str, owner: str, name: str, page: int, since: str
    ) -> list[dict[str, Any]]:
        assert self.issues_allowed
        self.calls.append(("issues", page))
        return self.issue_pages.get(page, [])

    async def issue(self, token: str, owner: str, name: str, number: int) -> dict[str, Any]:
        assert self.issues_allowed
        return issue(number)


@pytest.fixture
async def enriched(pipeline: Pipeline) -> AsyncIterator[Pipeline]:  # noqa: F811
    pipeline.repository = PipelineRepository(pipeline.repository.engine)
    pipeline.provider = EvidenceProvider()
    yield pipeline


async def insert_pr(value: Pipeline, record: dict[str, Any], *, force: bool = False) -> Any:
    async with value.repository.transaction() as connection:
        await value.repository.tenant(connection, value.organization_id)
        return await value.repository.upsert_pull_request(
            connection,
            value.organization_id,
            value.integration_id,
            value.repository_id,
            normalize.pull_request(record, "team/repo-1"),
            force=force,
        )


async def drain(value: Pipeline, limit: int = 100) -> None:
    for _ in range(limit):
        if not await value.worker.run_once():
            assert not await value.rows(
                "SELECT * FROM forge.jobs WHERE state IN ('dead','retry','running')"
            )
            return
    pytest.fail("Enrichment did not converge")


async def test_reviews_transitions_squash_membership_and_files_are_durable(
    enriched: Pipeline,
) -> None:
    source = pr(1, state="closed")
    source.update(merged_at=source["closed_at"], merge_commit_sha="2".zfill(40), commits=1)
    enriched.provider.detail = source
    enriched.provider.timelines = {
        1: [  # type: ignore[attr-defined]
            {
                "id": 40,
                "event": "reopened",
                "created_at": source["updated_at"],
                "actor": {"login": "developer", "type": "User"},
            },
            {"id": 41, "event": "merged", "created_at": source["updated_at"], "actor": None},
        ]
    }
    await insert_pr(enriched, source)
    await drain(enriched)
    row = (await enriched.rows("SELECT * FROM forge.pull_requests"))[0]
    assert row["reviews_status"] == row["transitions_status"] == row["commits_status"] == "complete"
    assert (
        row["issues_status"] == "unavailable"
        and row["issues_error"] == "issues_permission_required"
    )
    links = await enriched.rows("SELECT relationship FROM forge.pull_request_commits")
    assert {link["relationship"] for link in links} == {"head", "merge"}
    commits = await enriched.rows("SELECT * FROM forge.commits")
    assert len(commits) == 2 and all(item["files_status"] == "complete" for item in commits)
    assert all(item["total_changes"] == 6 for item in commits)
    assert {
        item["kind"] for item in await enriched.rows("SELECT * FROM forge.pull_request_transitions")
    } == {"opened", "reopened", "merged"}
    assert len(await enriched.rows("SELECT * FROM forge.commit_files")) == 2
    assert not any(call[0] == "issues" for call in enriched.provider.calls)


async def test_revision_fences_pages_and_known_approval_survives_dismissal(
    enriched: Pipeline,
) -> None:
    source = pr(1)
    enriched.provider.detail = source
    await insert_pr(enriched, source)
    await enriched.worker.run_once()  # Details checkpoint.
    lease = await enriched.repository.claim()
    assert lease
    work = await enriched.repository.load(lease)
    assert work
    page = await enriched.worker.fetch(work)
    newer = {**source, "updated_at": datetime.now(UTC).isoformat()}
    await insert_pr(enriched, newer)
    with pytest.raises(LostLease):
        await enriched.worker.persist(lease, work, page)
    assert not await enriched.rows("SELECT * FROM forge.pull_request_reviews")
    enriched.provider.detail = newer
    await drain(enriched)
    before = (await enriched.rows("SELECT * FROM forge.pull_request_reviews"))[0]
    enriched.provider.review_pages = {1: [review(1, "DISMISSED"), review(2, "DISMISSED")]}  # type: ignore[attr-defined]
    await enriched.webhook(
        "pull_request_review", {"repository": {"id": 1}, "pull_request": {"number": 1}}
    )
    await drain(enriched)
    rows = await enriched.rows("SELECT * FROM forge.pull_request_reviews ORDER BY provider_id")
    assert rows[0]["state"] == "DISMISSED" and rows[0]["approved_at"] == before["approved_at"]
    assert rows[0]["original_state"] == "APPROVED"
    assert rows[1]["approved_at"] is None and rows[1]["original_state"] is None


async def test_review_and_file_pages_checkpoint_before_completeness(enriched: Pipeline) -> None:
    source = pr(1)
    enriched.provider.detail = source
    enriched.provider.review_pages = {1: [review(n) for n in range(1, 101)], 2: [review(101)]}  # type: ignore[attr-defined]
    enriched.provider.file_pages = {
        1: [{"filename": f"f{n}", "status": "added"} for n in range(100)],
        2: [{"filename": "last", "status": "added"}],
    }  # type: ignore[attr-defined]
    await insert_pr(enriched, source)
    await enriched.worker.run_once()
    await enriched.worker.run_once()
    assert len(await enriched.rows("SELECT * FROM forge.pull_request_reviews")) == 100
    row = (await enriched.rows("SELECT * FROM forge.pull_requests"))[0]
    assert row["reviews_status"] == "partial"
    job = (await enriched.rows("SELECT * FROM forge.jobs WHERE kind='enrichment'"))[0]
    assert job["payload"]["page"] == 2 and job["payload"]["stage"] == "reviews"
    await drain(enriched)
    assert len(await enriched.rows("SELECT * FROM forge.pull_request_reviews")) == 101
    assert len(await enriched.rows("SELECT * FROM forge.commit_files")) == 101
    assert (await enriched.rows("SELECT files_status FROM forge.commits"))[0][
        "files_status"
    ] == "complete"


async def test_permission_aware_issues_and_explicit_references(enriched: Pipeline) -> None:
    source = pr(1)
    enriched.provider.detail = source
    enriched.provider.issues_allowed = True  # type: ignore[attr-defined]
    enriched.provider.timelines = {
        1: [
            {  # type: ignore[attr-defined]
                "event": "cross-referenced",
                "created_at": "2026-01-03T00:00:00Z",
                "source": {"type": "issue", "issue": issue(2)},
            }
        ]
    }
    await insert_pr(enriched, source)
    await drain(enriched)
    assert len(await enriched.rows("SELECT * FROM forge.issues")) == 1
    assert len(await enriched.rows("SELECT * FROM forge.issue_pull_requests")) == 1
    assert (await enriched.rows("SELECT issues_status FROM forge.pull_requests"))[0][
        "issues_status"
    ] == "complete"
    assert (await enriched.rows("SELECT links_status FROM forge.issues"))[0][
        "links_status"
    ] == "complete"


async def test_manual_repository_pass_repairs_previously_unresolved_issue_link(
    enriched: Pipeline,
) -> None:
    enriched.provider.issues_allowed = True  # type: ignore[attr-defined]
    enriched.provider.issue_pages = {1: [issue(2)]}  # type: ignore[attr-defined]
    enriched.provider.timelines = {
        2: [
            {  # type: ignore[attr-defined]
                "event": "cross-referenced",
                "created_at": "2026-01-03T00:00:00Z",
                "source": {
                    "type": "issue",
                    "issue": {
                        "number": 1,
                        "pull_request": {},
                        "html_url": "https://github.com/team/repo-1/pull/1",
                    },
                },
            }
        ]
    }
    async with enriched.repository.transaction() as connection:
        await enriched.repository.tenant(connection, enriched.organization_id)
        await enriched.repository.upsert_issue(
            connection,
            enriched.organization_id,
            enriched.integration_id,
            enriched.repository_id,
            normalize.issue(issue(2), "team/repo-1"),
        )
    await drain(enriched)
    assert (await enriched.rows("SELECT links_status FROM forge.issues"))[0][
        "links_status"
    ] == "partial"
    source = pr(1)
    enriched.provider.detail = source
    await insert_pr(enriched, source)
    await drain(enriched)
    assert not await enriched.rows("SELECT * FROM forge.issue_pull_requests")
    async with enriched.repository.transaction() as connection:
        await enriched.repository.tenant(connection, enriched.organization_id)
        repository = (
            await enriched.repository.many(
                connection,
                "SELECT * FROM forge.repositories WHERE id=:id",
                id=enriched.repository_id,
            )
        )[0]
        await enriched.repository.queue_enrichment(
            connection,
            enriched.organization_id,
            enriched.integration_id,
            enriched.repository_id,
            "repository",
            repository,
            force=True,
        )
    await drain(enriched)
    assert len(await enriched.rows("SELECT * FROM forge.issue_pull_requests")) == 1
    assert (await enriched.rows("SELECT links_status FROM forge.issues"))[0][
        "links_status"
    ] == "complete"


async def test_manual_sync_enriches_legacy_rows_and_never_demo(enriched: Pipeline) -> None:
    async with enriched.repository.transaction() as connection:
        await enriched.repository.tenant(connection, enriched.organization_id)
        # Simulate Phase 3 data without creating any enrichment job.
        await enriched.repository.upsert_pull_request(
            connection,
            enriched.organization_id,
            enriched.integration_id,
            enriched.repository_id,
            normalize.pull_request(pr(1), "team/repo-1"),
            schedule=False,
        )
    enriched.provider.detail = (enriched.provider.prs[1])[0]
    # Use the same revision for authoritative detail and incoming history.
    existing = (await enriched.rows("SELECT updated_at FROM forge.pull_requests"))[0]["updated_at"]
    enriched.provider.detail["updated_at"] = (existing + timedelta(seconds=1)).isoformat()
    await enriched.queue()
    await drain(enriched)
    assert (await enriched.rows("SELECT reviews_status FROM forge.pull_requests"))[0][
        "reviews_status"
    ] == "complete"
    await enriched.execute("UPDATE forge.repositories SET is_demo=true")
    calls = len(enriched.provider.calls)
    await enriched.queue()
    await enriched.worker.run_once()
    assert len(enriched.provider.calls) == calls


async def test_same_repository_foreign_keys_and_revocation_guard(enriched: Pipeline) -> None:
    source = pr(1)
    enriched.provider.detail = source
    parent = await insert_pr(enriched, source)
    async with enriched.repository.transaction() as connection:
        await enriched.repository.tenant(connection, enriched.organization_id)
        with pytest.raises(IntegrityError):
            await enriched.repository.upsert_review(
                connection,
                enriched.organization_id,
                uuid4(),
                parent["id"],
                normalize.review(review(1), "team/repo-1", 1),
            )
    lease = await enriched.repository.claim()
    assert lease
    work = await enriched.repository.load(lease)
    assert work
    page = await enriched.worker.fetch(work)
    await enriched.execute("UPDATE forge.repositories SET selected=false")
    assert await enriched.worker.persist(lease, work, page) == "canceled"
    assert not await enriched.rows("SELECT * FROM forge.pull_request_reviews")


async def test_provider_caps_remain_partial_and_shared_commit_links_are_allowed(
    enriched: Pipeline,
) -> None:
    source = pr(1)
    source["commits"] = 300
    enriched.provider.detail = source
    parent = await insert_pr(enriched, source)
    await enriched.worker.run_once()
    # Start at the final provider membership page without fetching 250 redundant fixtures.
    await enriched.execute("""UPDATE forge.jobs SET payload=jsonb_set(jsonb_set(payload,
        '{stage}','\"members\"'::jsonb),'{page}','3'::jsonb) WHERE kind='enrichment'""")
    enriched.provider.members = {3: [commit(n) for n in range(1, 51)]}  # type: ignore[attr-defined]
    await enriched.worker.run_once()
    # Finish only the PR job; file children are independently durable.
    await enriched.execute(
        "UPDATE forge.jobs SET available_at=now()+interval '1 hour' WHERE payload->>'kind'='commit'"
    )
    await enriched.worker.run_once()
    current = (await enriched.rows("SELECT * FROM forge.pull_requests"))[0]
    assert (
        current["commits_status"] == "partial"
        and current["commits_error"] == "provider_commit_limit"
    )
    second = await insert_pr(enriched, {**source, "id": 10002, "number": 2})
    shared = (await enriched.rows("SELECT * FROM forge.commits LIMIT 1"))[0]
    async with enriched.repository.transaction() as connection:
        await enriched.repository.tenant(connection, enriched.organization_id)
        await enriched.repository.link_commit(
            connection,
            enriched.organization_id,
            enriched.repository_id,
            second["id"],
            shared["id"],
            "head",
            shared["html_url"],
        )
        await enriched.repository.link_commit(
            connection,
            enriched.organization_id,
            enriched.repository_id,
            parent["id"],
            shared["id"],
            "merge",
            shared["html_url"],
        )
    assert (
        len(
            await enriched.rows(
                "SELECT * FROM forge.pull_request_commits WHERE commit_id=:id", id=shared["id"]
            )
        )
        == 3
    )
