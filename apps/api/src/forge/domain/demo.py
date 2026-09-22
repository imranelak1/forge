"""Deterministic, explicitly synthetic engineering history for local demo tenants."""

from datetime import datetime, timedelta
from hashlib import sha1
from typing import Any
from uuid import UUID, uuid5

VERSION = "phase4-v1"
TABLES = (
    "repositories",
    "pull_requests",
    "commits",
    "pull_request_reviews",
    "pull_request_transitions",
    "pull_request_commits",
    "commit_files",
    "issues",
    "issue_pull_requests",
    "sync_runs",
)


def identifier(organization: UUID, key: str) -> UUID:
    return uuid5(organization, f"demo:{VERSION}:{key}")


def history(
    organization: UUID, integration: UUID, anchor: datetime, repositories: int
) -> dict[str, list[dict[str, Any]]]:
    """Generate facts, never metric values. Empty source URLs have no live counterpart."""
    rows: dict[str, list[dict[str, Any]]] = {table: [] for table in TABLES}

    def add(table: str, key: str, **values: Any) -> UUID:
        row_id = identifier(organization, key)
        rows[table].append({"organization_id": organization, "id": row_id, **values})
        return row_id

    def coverage(prefix: str, status: str = "complete") -> dict[str, Any]:
        return {
            f"{prefix}_status": status,
            f"{prefix}_synced_at": anchor,
            f"{prefix}_error": "demo_partial_evidence" if status == "partial" else None,
        }

    authors = ("maya-demo", "alex-demo", "sam-demo", "riley-demo")
    changes = (
        "Preserve request context during retries",
        "Index repository activity by organization",
        "Bound the webhook delivery queue",
        "Add review history to change details",
        "Handle missing provider timestamps",
        "Keep filter state in the page URL",
        "Make organization switching accessible",
        "Reconcile commits after a force push",
        "Reduce query count on the overview",
        "Track source coverage for imports",
        "Restore focus after closing a dialog",
        "Validate cursor scope before paging",
    )
    for repo_index in range(repositories):
        key = f"repository:{repo_index}"
        repo_id = identifier(organization, key)
        name = ("api-service", "web-client")[repo_index % 2]
        add(
            "repositories",
            key,
            integration_id=integration,
            provider_id=9_000_000_100 + repo_index,
            owner="forge-demo",
            name=name,
            full_name=f"forge-demo/{name}",
            html_url="",
            description="Generated 90-day demonstration history. No live GitHub source.",
            language="Python" if repo_index == 0 else "TypeScript",
            default_branch="main",
            is_private=False,
            archived=False,
            authorized=False,
            selected=True,
            is_demo=True,
            pushed_at=anchor - timedelta(hours=2),
            last_synced_at=anchor,
            **coverage("issues"),
        )
        for index in range(45):
            pr_key = f"{key}:pr:{index}"
            opened = anchor - timedelta(days=89 - 2 * index, hours=3 + repo_index)
            cycle_hours = (4, 8, 12, 20, 32, 48, 72, 96, 144)[index % 9]
            is_open = index >= 40
            unmerged = index % 13 == 0
            closed = (
                None
                if is_open
                else min(opened + timedelta(hours=cycle_hours), anchor - timedelta(hours=1))
            )
            merged = None if is_open or unmerged else closed
            author = authors[index % len(authors)]
            sha = sha1(f"{organization}:{pr_key}:head".encode(), usedforsecurity=False).hexdigest()
            merge_sha = (
                sha1(f"{organization}:{pr_key}:merge".encode(), usedforsecurity=False).hexdigest()
                if merged
                else None
            )
            title = changes[index % len(changes)]
            pr_id = add(
                "pull_requests",
                pr_key,
                repository_id=repo_id,
                provider_id=9_000_001_000 + repo_index * 100 + index,
                number=index + 1,
                title=title,
                state="open" if is_open else "closed",
                draft=is_open and index % 2 == 0,
                author_login=author,
                author_type="User",
                head_sha=sha,
                base_ref="main",
                opened_at=opened,
                updated_at=closed or anchor - timedelta(hours=index - 38),
                closed_at=closed,
                merged_at=merged,
                merge_commit_sha=merge_sha,
                provider_commit_count=1,
                html_url="",
                **coverage("reviews", "partial" if index % 17 == 0 else "complete"),
                **coverage("transitions"),
                **coverage("commits"),
                **coverage("issues"),
            )
            for kind, commit_sha, occurred in (
                ("head", sha, opened + timedelta(hours=1)),
                *(([("merge", merge_sha, merged)]) if merged else []),
            ):
                commit_id = add(
                    "commits",
                    f"{pr_key}:commit:{kind}",
                    repository_id=repo_id,
                    sha=commit_sha,
                    message=title if kind == "head" else f"Merge #{index + 1}: {title}",
                    author_login=author,
                    authored_at=occurred,
                    committed_at=occurred,
                    html_url="",
                    additions=20 + index,
                    deletions=4 + index % 8,
                    total_changes=24 + index + index % 8,
                    **coverage("files"),
                )
                add(
                    "pull_request_commits",
                    f"{pr_key}:link:{kind}",
                    repository_id=repo_id,
                    pull_request_id=pr_id,
                    commit_id=commit_id,
                    relationship=kind,
                    html_url="",
                )
                for file_index, filename in enumerate(("src/service.py", "tests/test_service.py")):
                    additions = 12 + index if file_index == 0 else 8
                    deletions = 4 + index % 8 if file_index == 0 else 0
                    add(
                        "commit_files",
                        f"{pr_key}:commit:{kind}:file:{file_index}",
                        repository_id=repo_id,
                        commit_id=commit_id,
                        filename=filename,
                        previous_filename=None,
                        status="modified",
                        additions=additions,
                        deletions=deletions,
                        changes=additions + deletions,
                    )
            # Reuse an explicit member commit in another PR to exercise the many-to-many grain.
            if index == 8:
                add(
                    "pull_request_commits",
                    f"{pr_key}:shared",
                    repository_id=repo_id,
                    pull_request_id=pr_id,
                    commit_id=identifier(organization, f"{key}:pr:7:commit:head"),
                    relationship="head",
                    html_url="",
                )
                rows["pull_requests"][-1]["provider_commit_count"] = 2
            if index % 11 != 0:
                review_at = min(
                    opened + timedelta(hours=max(1, cycle_hours // 4)),
                    anchor - timedelta(hours=1),
                )
                review_state = "CHANGES_REQUESTED" if index % 4 == 0 else "COMMENTED"
                add(
                    "pull_request_reviews",
                    f"{pr_key}:review:comment",
                    repository_id=repo_id,
                    pull_request_id=pr_id,
                    provider_id=9_000_010_000 + repo_index * 1000 + index * 3,
                    reviewer_login=authors[(index + 1) % len(authors)],
                    reviewer_type="User",
                    state=review_state,
                    original_state=review_state,
                    submitted_at=review_at,
                    approved_at=None,
                    dismissed_at=None,
                    html_url="",
                    observed_at=anchor,
                )
                if index % 7 != 0:
                    approval = min(
                        opened + timedelta(hours=max(2, cycle_hours // 2)),
                        anchor - timedelta(minutes=30),
                    )
                    dismissed = index % 9 == 0
                    unknown = index % 19 == 0
                    add(
                        "pull_request_reviews",
                        f"{pr_key}:review:approval",
                        repository_id=repo_id,
                        pull_request_id=pr_id,
                        provider_id=9_000_010_001 + repo_index * 1000 + index * 3,
                        reviewer_login=authors[(index + 2) % len(authors)],
                        reviewer_type="User",
                        state="DISMISSED" if dismissed or unknown else "APPROVED",
                        original_state=None if unknown else "APPROVED",
                        submitted_at=approval,
                        approved_at=None if unknown else approval,
                        dismissed_at=approval + timedelta(minutes=30) if dismissed else None,
                        html_url="",
                        observed_at=anchor,
                    )
            # Bot/self reviews are stored evidence, never qualifying human review samples.
            add(
                "pull_request_reviews",
                f"{pr_key}:review:bot",
                repository_id=repo_id,
                pull_request_id=pr_id,
                provider_id=9_000_010_002 + repo_index * 1000 + index * 3,
                reviewer_login="checks-demo[bot]",
                reviewer_type="Bot",
                state="COMMENTED",
                original_state="COMMENTED",
                submitted_at=opened + timedelta(minutes=10),
                approved_at=None,
                dismissed_at=None,
                html_url="",
                observed_at=anchor,
            )
            if index % 10 == 0:
                add(
                    "pull_request_reviews",
                    f"{pr_key}:review:self",
                    repository_id=repo_id,
                    pull_request_id=pr_id,
                    provider_id=9_000_030_000 + repo_index * 100 + index,
                    reviewer_login=author,
                    reviewer_type="User",
                    state="COMMENTED",
                    original_state="COMMENTED",
                    submitted_at=opened + timedelta(minutes=15),
                    approved_at=None,
                    dismissed_at=None,
                    html_url="",
                    observed_at=anchor,
                )
            transitions: list[tuple[str, datetime]] = []
            if index % 6 == 0:
                transitions.extend(
                    (
                        ("converted_to_draft", opened + timedelta(minutes=10)),
                        ("ready_for_review", opened + timedelta(minutes=40)),
                    )
                )
            if index % 8 == 0:
                transitions.extend(
                    (
                        ("closed", opened + timedelta(hours=1)),
                        ("reopened", opened + timedelta(hours=2)),
                    )
                )
            if closed:
                transitions.append(("merged" if merged else "closed", closed))
            for event_index, (kind, occurred) in enumerate(transitions):
                event_key = f"{pr_key}:transition:{event_index}"
                add(
                    "pull_request_transitions",
                    event_key,
                    repository_id=repo_id,
                    pull_request_id=pr_id,
                    provider_id=None,
                    source_key=event_key,
                    kind=kind,
                    occurred_at=occurred,
                    actor_login=author,
                    actor_type="User",
                    html_url="",
                )
            if index % 3 == 0:
                issue_id = add(
                    "issues",
                    f"{pr_key}:issue",
                    repository_id=repo_id,
                    provider_id=9_000_020_000 + repo_index * 100 + index,
                    number=100 + index,
                    title=f"Investigate: {title.lower()}",
                    state="closed" if merged else "open",
                    author_login=authors[(index + 2) % len(authors)],
                    author_type="User",
                    opened_at=opened - timedelta(hours=12),
                    updated_at=merged or opened,
                    closed_at=merged,
                    html_url="",
                    **coverage("links"),
                )
                add(
                    "issue_pull_requests",
                    f"{pr_key}:issue-link",
                    repository_id=repo_id,
                    issue_id=issue_id,
                    pull_request_id=pr_id,
                    relationship="references",
                    source_key=f"demo:{pr_key}:reference",
                    occurred_at=opened,
                    html_url="",
                )
        add(
            "sync_runs",
            f"{key}:history",
            integration_id=integration,
            repository_id=repo_id,
            kind="history",
            status="succeeded",
            stage="commits",
            since=anchor - timedelta(days=90),
            until=anchor,
            repositories_processed=1,
            pull_requests_processed=45,
            commits_processed=sum(row["repository_id"] == repo_id for row in rows["commits"]),
            created_at=anchor,
            started_at=anchor,
            finished_at=anchor,
        )
    return rows
