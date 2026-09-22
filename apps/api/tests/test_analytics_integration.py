"""Hand-computed analytics over real PostgreSQL, with actual sessions and tenant RLS."""

import os
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import IntegrityError, ProgrammingError
from test_auth import PREFIX, AuthHarness, Identity
from test_auth import auth as auth_fixture

auth = auth_fixture
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("FORGE_RUN_DB_TESTS") != "1", reason="Dedicated test database required"
    ),
]
START = datetime(2026, 1, 1, tzinfo=UTC)
END = START + timedelta(days=2)
MERGED = START + timedelta(days=1)
HOUR = timedelta(hours=1)
WINDOW = {"from": START.isoformat(), "to": END.isoformat()}


@dataclass
class Facts:
    auth: AuthHarness
    owner: Identity
    organization: UUID
    integration: UUID
    repository: UUID
    number: int = 0

    @property
    def path(self) -> str:
        return f"{PREFIX}/organizations/{self.organization}"

    async def insert(self, table: str, values: dict[str, Any]) -> UUID:
        identifier = values.setdefault("id", uuid4())
        values.setdefault("organization_id", self.organization)
        storage = self.auth.app.state.identity_service.repository
        async with storage.transaction() as connection:
            await storage.tenant(connection, self.organization)
            await storage.execute(
                connection,
                f"INSERT INTO forge.{table} ({','.join(values)}) "
                f"VALUES ({','.join(':' + key for key in values)})",
                **values,
            )
        return identifier

    async def update(self, table: str, identifier: UUID, **values: Any) -> None:
        storage = self.auth.app.state.identity_service.repository
        async with storage.transaction() as connection:
            await storage.tenant(connection, self.organization)
            await storage.execute(
                connection,
                f"UPDATE forge.{table} SET {','.join(key + '=:' + key for key in values)} "
                "WHERE organization_id=:org AND id=:id",
                **values,
                org=self.organization,
                id=identifier,
            )

    async def repo(self, **overrides: Any) -> UUID:
        return await self.insert(
            "repositories",
            {
                "integration_id": self.integration,
                "provider_id": secrets.randbelow(2**50) + 1,
                "owner": "synthetic",
                "name": "analytics",
                "full_name": "synthetic/analytics",
                "html_url": "",
                "default_branch": "main",
                "is_private": False,
                "archived": False,
                "selected": True,
                "authorized": False,
                "is_demo": True,
                "last_synced_at": END,
                "issues_status": "unavailable",
                "issues_error": "permissions_required",
                **overrides,
            },
        )

    async def pr(self, hours: float = 1, **overrides: Any) -> UUID:
        self.number += 1
        return await self.insert(
            "pull_requests",
            {
                "repository_id": self.repository,
                "provider_id": secrets.randbelow(2**50) + 1,
                "number": self.number,
                "title": f"Evidence {self.number}",
                "state": "closed",
                "draft": False,
                "author_login": "author",
                "author_type": "User",
                "head_sha": f"{self.number:040x}",
                "base_ref": "main",
                "opened_at": MERGED - HOUR * hours,
                "updated_at": MERGED,
                "merged_at": MERGED,
                "closed_at": MERGED,
                "html_url": "",
                "reviews_status": "complete",
                "transitions_status": "complete",
                "commits_status": "complete",
                "issues_status": "unavailable",
                "issues_error": "permissions_required",
                **overrides,
            },
        )

    async def review(self, pull_request: UUID, at: datetime | None, **overrides: Any) -> UUID:
        state = overrides.get("state", "APPROVED")
        return await self.insert(
            "pull_request_reviews",
            {
                "repository_id": self.repository,
                "pull_request_id": pull_request,
                "provider_id": secrets.randbelow(2**50) + 1,
                "reviewer_login": "reviewer",
                "reviewer_type": "User",
                "state": state,
                "original_state": state
                if state in {"COMMENTED", "APPROVED", "CHANGES_REQUESTED"}
                else None,
                "submitted_at": at,
                "approved_at": at if state == "APPROVED" else None,
                "html_url": "",
                **overrides,
            },
        )

    async def commit(self, **overrides: Any) -> UUID:
        return await self.insert(
            "commits",
            {
                "repository_id": self.repository,
                "sha": secrets.token_hex(20),
                "message": "Synthetic commit with no source contents",
                "author_login": "author",
                "authored_at": MERGED - HOUR,
                "committed_at": MERGED,
                "html_url": "",
                "files_status": "complete",
                "additions": 5,
                "deletions": 2,
                "total_changes": 7,
                **overrides,
            },
        )

    async def issue(self, **overrides: Any) -> UUID:
        self.number += 1
        return await self.insert(
            "issues",
            {
                "repository_id": self.repository,
                "provider_id": secrets.randbelow(2**50) + 1,
                "number": self.number,
                "title": "Explicit issue",
                "state": "open",
                "author_login": "author",
                "author_type": "User",
                "opened_at": START,
                "updated_at": MERGED,
                "html_url": "",
                **overrides,
            },
        )


@pytest.fixture
async def facts(auth: AuthHarness) -> Facts:
    owner = await auth.register()
    await auth.verify(owner)
    organization = UUID(await auth.organization(owner))
    item = Facts(auth, owner, organization, uuid4(), uuid4())
    await item.insert(
        "integrations",
        {
            "id": item.integration,
            "installation_id": secrets.randbelow(2**50) + 1,
            "account_login": "synthetic",
            "account_type": "Organization",
            "status": "disconnected",
        },
    )
    item.repository = await item.repo()
    await item.insert(
        "sync_runs",
        {
            "integration_id": item.integration,
            "repository_id": item.repository,
            "kind": "history",
            "status": "succeeded",
            "stage": "commits",
            "since": START,
            "until": END,
            "finished_at": END,
        },
    )
    return item


async def test_exact_percentiles_same_cohort_exclusions_and_reopened_wall_clock(facts: Facts):
    one = await facts.pr(1)
    two = await facts.pr(2)
    four = await facts.pr(4)
    await facts.pr(8)
    await facts.pr(-1)  # Invalid negative cycle duration is a cohort exclusion.
    await facts.review(one, MERGED - HOUR * 0.75)
    await facts.review(two, MERGED - HOUR * 1.5, state="COMMENTED")
    await facts.review(two, MERGED - HOUR)
    await facts.review(four, MERGED - HOUR * 3.9, reviewer_type="Bot")
    await facts.review(four, MERGED - HOUR * 3.8, reviewer_login="AUTHOR")
    await facts.review(four, None, state="PENDING")
    await facts.review(four, MERGED - HOUR * 3, state="CHANGES_REQUESTED")
    await facts.review(
        four,
        MERGED - HOUR * 2,
        state="DISMISSED",
        original_state="APPROVED",
        approved_at=MERGED - HOUR * 2,
        dismissed_at=MERGED - HOUR,
    )
    for kind, at in (("closed", MERGED - HOUR * 2), ("reopened", MERGED - HOUR)):
        await facts.insert(
            "pull_request_transitions",
            {
                "repository_id": facts.repository,
                "pull_request_id": four,
                "source_key": kind,
                "kind": kind,
                "occurred_at": at,
                "actor_login": "author",
                "html_url": "",
            },
        )
    response = await facts.owner.client.get(facts.path + "/metrics/pull-requests", params=WINDOW)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["merged_count"] == 5
    expected = {
        "cycle_time": (4, 1, 3.75, 3, 5, 7.4),
        "review_wait": (3, 2, 7 / 12, 0.5, 0.75, 0.95),
        "approval_to_merge": (3, 2, 1.25, 1, 1.5, 1.9),
    }
    for key, values in expected.items():
        metric = data["metrics"][key]
        assert (metric["sample_count"], metric["excluded_count"]) == values[:2]
        for field, hours in zip(
            ("mean_seconds", "median_seconds", "p75_seconds", "p95_seconds"),
            values[2:],
            strict=True,
        ):
            assert metric[field] == pytest.approx(hours * 3600)
        evidence = await facts.owner.client.get(
            facts.path + "/pull-requests", params={**WINDOW, "metric": key}
        )
        assert evidence.status_code == 200, evidence.text
        items = evidence.json()["items"]
        assert len(items) == metric["sample_count"]
        assert sum(row["durations"][key] for row in items) / len(items) == pytest.approx(
            metric["mean_seconds"]
        )
    assert data["metrics"]["review_wait"]["exclusions"] == {
        "invalid_timestamps": 1,
        "missing_review": 1,
    }
    assert data["coverage"]["dismissed_approval_count"] == 1
    assert data["trend"][0]["merged_count"] == 0 and data["trend"][1]["merged_count"] == 5
    detail = (await facts.owner.client.get(facts.path + f"/pull-requests/{four}")).json()
    assert detail["pull_request"]["durations"]["cycle_time"] == 4 * 3600
    assert detail["pull_request"]["approval_dismissed"]
    assert detail["counts"]["transitions"] == 2


async def test_half_open_merge_window_author_filter_and_open_age_are_independent(facts: Facts):
    lower = await facts.pr(
        1, merged_at=START, opened_at=START - HOUR, updated_at=START, author_login="SelectedAuthor"
    )
    await facts.pr(1, merged_at=END, opened_at=END - HOUR, updated_at=END)
    opened = await facts.pr(
        1,
        state="open",
        merged_at=None,
        closed_at=None,
        opened_at=START - timedelta(days=50),
        author_login="SelectedAuthor",
    )
    result = (
        await facts.owner.client.get(
            facts.path + "/metrics/pull-requests", params={**WINDOW, "author": "selectedauthor"}
        )
    ).json()
    assert result["merged_count"] == 1 and result["metrics"]["cycle_time"]["mean_seconds"] == 3600
    assert result["open_queue"]["count"] == 1
    assert result["open_queue"]["oldest"][0]["id"] == str(opened)
    assert result["open_queue"]["age"]["mean_seconds"] > 50 * 86400
    rows = (
        await facts.owner.client.get(
            facts.path + "/pull-requests",
            params={**WINDOW, "cohort": "merged", "author": "SELECTEDAUTHOR"},
        )
    ).json()["items"]
    assert [row["id"] for row in rows] == [str(lower)]


async def test_unknown_dismissed_and_partial_reviews_are_not_fabricated_first_approvals(
    facts: Facts,
):
    unknown = await facts.pr(4)
    await facts.review(unknown, MERGED - HOUR * 3, state="DISMISSED")
    await facts.review(unknown, MERGED - HOUR)
    partial = await facts.pr(4, reviews_status="partial", reviews_error="capacity_exceeded")
    await facts.review(partial, MERGED - HOUR * 2)
    data = (
        await facts.owner.client.get(facts.path + "/metrics/pull-requests", params=WINDOW)
    ).json()
    for key in ("review_wait", "approval_to_merge"):
        assert data["metrics"][key]["sample_count"] == 0
        assert data["metrics"][key]["median_seconds"] is None
        assert data["metrics"][key]["exclusions"] == {
            "unknown_dismissed_review": 1,
            "incomplete_reviews": 1,
        }
    assert data["coverage"]["status"] == "partial"
    assert data["coverage"]["reviews_incomplete"] == 1
    assert data["coverage"]["unknown_dismissed_review_count"] == 1
    excluded = (
        await facts.owner.client.get(
            facts.path + "/pull-requests",
            params={**WINDOW, "metric": "approval_to_merge", "eligibility": "excluded"},
        )
    ).json()["items"]
    assert len(excluded) == 2 and all(
        row["durations"]["approval_to_merge"] is None for row in excluded
    )


async def test_later_unknown_dismissal_does_not_obscure_an_earlier_known_review(facts: Facts):
    identifier = await facts.pr(4)
    await facts.review(identifier, MERGED - HOUR * 3, state="COMMENTED")
    await facts.review(identifier, MERGED - HOUR * 2, state="DISMISSED")
    await facts.review(identifier, MERGED - HOUR)
    row = (await facts.owner.client.get(facts.path + f"/pull-requests/{identifier}")).json()[
        "pull_request"
    ]
    assert row["durations"]["review_wait"] == 3600
    assert row["durations"]["approval_to_merge"] is None


async def test_zero_samples_and_missing_issues_permission_are_explicit(facts: Facts):
    response = await facts.owner.client.get(facts.path + "/metrics/pull-requests", params=WINDOW)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["merged_count"] == data["open_queue"]["count"] == 0
    assert all(item["mean_seconds"] is None for item in data["metrics"].values())
    issues = await facts.owner.client.get(
        facts.path + f"/repositories/{facts.repository}/issues", params=WINDOW
    )
    assert issues.status_code == 200, issues.text
    assert issues.json()["items"] == []
    assert issues.json()["coverage"]["status"] == "unavailable"
    assert issues.json()["coverage"]["error_code"] == "permissions_required"


@pytest.mark.parametrize("status", ["suspended", "needs_attention", "disconnected"])
async def test_inactive_source_marks_retained_history_partial_but_demo_is_exempt(
    facts: Facts, status: str
):
    await facts.update("repositories", facts.repository, is_demo=False, authorized=True)
    await facts.update("integrations", facts.integration, status="active")
    path = facts.path + "/metrics/pull-requests"
    active = await facts.owner.client.get(path, params=WINDOW)
    assert active.status_code == 200, active.text
    assert active.json()["coverage"]["status"] == "complete"
    await facts.update("integrations", facts.integration, status=status)
    unavailable = await facts.owner.client.get(path, params=WINDOW)
    assert unavailable.status_code == 200, unavailable.text
    assert unavailable.json()["coverage"]["status"] == "partial"
    assert "source_access_unavailable" in unavailable.json()["coverage"]["limitations"]
    await facts.update("repositories", facts.repository, is_demo=True, authorized=False)
    demo = await facts.owner.client.get(path, params=WINDOW)
    assert demo.status_code == 200, demo.text
    assert demo.json()["coverage"]["status"] == "complete"


async def test_selected_scope_retains_explicit_historical_detail_access(facts: Facts):
    selected = await facts.pr(1)
    old_repo = await facts.repo(selected=False)
    old = await facts.pr(10, repository_id=old_repo)
    data = (
        await facts.owner.client.get(facts.path + "/metrics/pull-requests", params=WINDOW)
    ).json()
    assert data["metrics"]["cycle_time"]["sample_count"] == 1
    assert data["metrics"]["cycle_time"]["mean_seconds"] == 3600
    listed = (await facts.owner.client.get(facts.path + "/pull-requests", params=WINDOW)).json()[
        "items"
    ]
    assert [row["id"] for row in listed] == [str(selected)]
    historical = await facts.owner.client.get(facts.path + f"/pull-requests/{old}")
    assert historical.status_code == 200 and historical.json()["pull_request"]["html_url"] is None
    explicit = (
        await facts.owner.client.get(
            facts.path + "/metrics/pull-requests", params={**WINDOW, "repository": str(old_repo)}
        )
    ).json()
    assert explicit["metrics"]["cycle_time"]["mean_seconds"] == 10 * 3600


async def test_cursor_pagination_is_stable_and_tenant_filter_bound(facts: Facts):
    identifiers = {str(await facts.pr(hours)) for hours in (1, 2, 3)}
    first = await facts.owner.client.get(
        facts.path + "/pull-requests", params={**WINDOW, "limit": 2}
    )
    assert first.status_code == 200, first.text
    page = first.json()
    assert page["next_cursor"]
    second = await facts.owner.client.get(
        facts.path + "/pull-requests", params={**WINDOW, "limit": 2, "cursor": page["next_cursor"]}
    )
    assert second.status_code == 200, second.text
    assert {row["id"] for row in page["items"] + second.json()["items"]} == identifiers
    assert second.json()["next_cursor"] is None
    changed = await facts.owner.client.get(
        facts.path + "/pull-requests",
        params={**WINDOW, "limit": 2, "cursor": page["next_cursor"], "author": "other"},
    )
    assert changed.status_code == 422 and changed.json()["code"] == "invalid_cursor"
    foreign = await facts.auth.register()
    other_org = await facts.auth.organization(foreign)
    cross = await foreign.client.get(
        f"{PREFIX}/organizations/{other_org}/pull-requests",
        params={**WINDOW, "limit": 2, "cursor": page["next_cursor"]},
    )
    assert cross.status_code == 422


async def test_squash_shared_commit_relations_count_distinct_entities_and_page_files(facts: Facts):
    first, second = await facts.pr(2), await facts.pr(3)
    commit = await facts.commit()
    squash = await facts.commit()
    for pr, item, relation in (
        (first, commit, "head"),
        (second, commit, "head"),
        (first, squash, "merge"),
        (first, squash, "head"),
    ):
        await facts.insert(
            "pull_request_commits",
            {
                "repository_id": facts.repository,
                "pull_request_id": pr,
                "commit_id": item,
                "relationship": relation,
                "html_url": "",
            },
        )
    for filename in ("one.py", "two.py", "three.py"):
        await facts.insert(
            "commit_files",
            {
                "repository_id": facts.repository,
                "commit_id": commit,
                "filename": filename,
                "status": "modified",
                "additions": 1,
                "deletions": 0,
                "changes": 1,
            },
        )
    detail = (await facts.owner.client.get(facts.path + f"/commits/{commit}")).json()["commit"]
    assert detail["pull_request_count"] == 2 and detail["changed_files"] == 3
    linked = (await facts.owner.client.get(facts.path + f"/pull-requests/{first}/commits")).json()[
        "items"
    ]
    assert len(linked) == 2
    assert (
        next(row for row in linked if row["id"] == str(squash))["relationship"]
        == "member_and_merge"
    )
    prs = (await facts.owner.client.get(facts.path + f"/commits/{commit}/pull-requests")).json()[
        "items"
    ]
    assert {row["id"] for row in prs} == {str(first), str(second)}
    files = (
        await facts.owner.client.get(facts.path + f"/commits/{commit}/files", params={"limit": 2})
    ).json()
    more = (
        await facts.owner.client.get(
            facts.path + f"/commits/{commit}/files",
            params={"limit": 2, "cursor": files["next_cursor"]},
        )
    ).json()
    assert len(files["items"] + more["items"]) == 3
    assert all(row["blob_url"] is None and "patch" not in row for row in files["items"])
    listing = await facts.owner.client.get(facts.path + "/commits", params=WINDOW)
    assert listing.status_code == 200 and len(listing.json()["items"]) == 2


async def test_explicit_issue_links_do_not_fan_out_metrics_and_evidence_is_tenant_scoped(
    facts: Facts,
):
    pr = await facts.pr(2)
    issue = await facts.issue()
    for source in ("reference-one", "reference-two"):
        await facts.insert(
            "issue_pull_requests",
            {
                "repository_id": facts.repository,
                "issue_id": issue,
                "pull_request_id": pr,
                "relationship": "references",
                "source_key": source,
                "occurred_at": MERGED,
                "html_url": "",
            },
        )
    assert (
        len(
            (await facts.owner.client.get(facts.path + f"/pull-requests/{pr}/issues")).json()[
                "items"
            ]
        )
        == 1
    )
    assert (
        len(
            (await facts.owner.client.get(facts.path + f"/issues/{issue}/pull-requests")).json()[
                "items"
            ]
        )
        == 1
    )
    detail = await facts.owner.client.get(facts.path + f"/issues/{issue}")
    assert detail.status_code == 200
    assert detail.json()["issue"]["links_coverage"]["status"] == "pending"
    outsider = await facts.auth.register()
    other = await facts.auth.organization(outsider)
    for resource in (
        f"pull-requests/{pr}",
        f"pull-requests/{pr}/reviews",
        f"issues/{issue}",
        f"issues/{issue}/pull-requests",
        f"repositories/{facts.repository}/issues",
    ):
        response = await outsider.client.get(f"{PREFIX}/organizations/{other}/{resource}")
        assert response.status_code == 404, response.text
    member = await facts.auth.register()
    await facts.auth.join(facts.owner, str(facts.organization), member, "viewer")
    assert (await member.client.get(facts.path + f"/pull-requests/{pr}")).status_code == 200


async def test_evidence_foreign_keys_require_same_repository_not_just_same_tenant(facts: Facts):
    pr = await facts.pr(2)
    other_repo = await facts.repo()
    other_commit = await facts.commit(repository_id=other_repo)
    other_issue = await facts.issue(repository_id=other_repo)
    with pytest.raises(IntegrityError):
        await facts.review(pr, MERGED - HOUR, repository_id=other_repo)
    with pytest.raises(IntegrityError):
        await facts.insert(
            "pull_request_commits",
            {
                "repository_id": facts.repository,
                "pull_request_id": pr,
                "commit_id": other_commit,
                "relationship": "head",
                "html_url": "",
            },
        )
    with pytest.raises(IntegrityError):
        await facts.insert(
            "issue_pull_requests",
            {
                "repository_id": facts.repository,
                "issue_id": other_issue,
                "pull_request_id": pr,
                "relationship": "references",
                "source_key": "invalid",
                "occurred_at": MERGED,
                "html_url": "",
            },
        )
    with pytest.raises(IntegrityError):
        await facts.insert(
            "commit_files",
            {
                "repository_id": facts.repository,
                "commit_id": other_commit,
                "filename": "no.py",
                "status": "added",
            },
        )
    with pytest.raises(ProgrammingError):
        await facts.review(pr, MERGED - HOUR, organization_id=uuid4())


@pytest.mark.parametrize("kind", ["reviews", "transitions"])
async def test_timeline_evidence_pages_chronologically_with_stable_tie_breaker(
    facts: Facts, kind: str
):
    pr = await facts.pr(4)
    identifiers = [UUID(int=value) for value in (90, 80, 2)]
    stamps = [MERGED - HOUR * 3, MERGED - HOUR * 3, MERGED - HOUR]
    for identifier, stamp in zip(identifiers, stamps, strict=True):
        if kind == "reviews":
            await facts.review(pr, stamp, id=identifier)
        else:
            await facts.insert(
                "pull_request_transitions",
                {
                    "id": identifier,
                    "repository_id": facts.repository,
                    "pull_request_id": pr,
                    "source_key": str(identifier),
                    "kind": "reopened",
                    "occurred_at": stamp,
                    "actor_login": "author",
                    "html_url": "",
                },
            )
    path = facts.path + f"/pull-requests/{pr}/{kind}"
    observed = []
    cursor = None
    for _ in range(3):
        response = await facts.owner.client.get(
            path, params={"limit": 1, **({"cursor": cursor} if cursor else {})}
        )
        assert response.status_code == 200, response.text
        result = response.json()
        observed.extend(row["id"] for row in result["items"])
        cursor = result["next_cursor"]
    assert observed == [str(identifiers[1]), str(identifiers[0]), str(identifiers[2])]
    assert cursor is None


async def test_extreme_window_validation_does_not_raise_server_error(facts: Facts):
    invalid = await facts.owner.client.get(
        facts.path + "/metrics/pull-requests", params={"to": "0001-01-01T00:00:00Z"}
    )
    assert invalid.status_code == 422 and invalid.json()["code"] == "invalid_window"
    valid = await facts.owner.client.get(
        facts.path + "/metrics/pull-requests",
        params={"from": "9999-12-30T00:00:00Z", "to": "9999-12-31T23:59:59Z"},
    )
    assert valid.status_code == 200, valid.text
    assert len(valid.json()["trend"]) == 2


async def test_unknown_reviewer_cannot_establish_first_human_review_or_approval(facts: Facts):
    unknown_first = await facts.pr(4)
    known_first = await facts.pr(4)
    await facts.review(unknown_first, MERGED - HOUR * 3, reviewer_login=None)
    await facts.review(unknown_first, MERGED - HOUR)
    await facts.review(known_first, MERGED - HOUR * 3)
    await facts.review(known_first, MERGED - HOUR, reviewer_type=None)
    response = await facts.owner.client.get(facts.path + "/metrics/pull-requests", params=WINDOW)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["coverage"]["unknown_reviewer_count"] == 1
    assert "unknown_reviewer" in data["coverage"]["limitations"]
    for metric in ("review_wait", "approval_to_merge"):
        assert data["metrics"][metric]["sample_count"] == 1
        assert data["metrics"][metric]["exclusions"] == {"unknown_reviewer": 1}
