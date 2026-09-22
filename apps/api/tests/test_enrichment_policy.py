from typing import Any

import httpx
import pytest
from test_github_provider import app_settings, installation  # noqa: F401

from forge.config import Settings
from forge.domain import github
from forge.integrations.github import GitHubApp, GitHubFailure


@pytest.mark.parametrize("allowed", [False, True])
async def test_issue_permission_is_optional_and_token_only_requests_existing_grants(
    app_settings: Settings,  # noqa: F811
    allowed: bool,
) -> None:
    requested: list[bytes] = []
    permissions = {"contents": "read", "pull_requests": "read"}
    if allowed:
        permissions["issues"] = "read"

    def transport(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json=installation(permissions=permissions))
        requested.append(request.content)
        return httpx.Response(201, json={"token": "fixture-token", "permissions": permissions})

    client = httpx.AsyncClient(transport=httpx.MockTransport(transport))
    provider = GitHubApp(app_settings)
    await provider.client.aclose()
    provider.client = client
    try:
        token, observed = await provider.enrichment_credentials(99)
        assert token == "fixture-token" and observed is allowed
        assert (b'"issues"' in requested[0]) is allowed
    finally:
        await client.aclose()


async def test_commit_metadata_discards_patches_and_download_urls_at_adapter_boundary(
    app_settings: Settings,  # noqa: F811
) -> None:
    paths = []

    def transport(request: httpx.Request) -> httpx.Response:
        paths.append(str(request.url))
        return httpx.Response(
            200,
            json={
                "sha": "a" * 40,
                "commit": {},
                "author": None,
                "stats": {"additions": 2, "deletions": 1, "total": 3},
                "files": [
                    {
                        "filename": "src/test.py",
                        "status": "modified",
                        "additions": 2,
                        "patch": "NEVER-PERSIST-SOURCE",
                        "raw_url": "https://evil.example/private",
                        "contents_url": "https://evil.example/contents",
                    }
                ],
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(transport))
    provider = GitHubApp(app_settings)
    await provider.client.aclose()
    provider.client = client
    try:
        result = await provider.commit_details("fixture-token", "team", "repo", "a" * 40, 2)
        assert result["files"] == [
            {"filename": "src/test.py", "status": "modified", "additions": 2}
        ]
        assert "NEVER-PERSIST" not in repr(result)
        assert paths == [
            f"https://api.github.com/repos/team/repo/commits/{'a' * 40}?per_page=100&page=2"
        ]
        with pytest.raises(GitHubFailure):
            await provider.commit_details("fixture-token", "team", "repo", "a" * 40, 31)
    finally:
        await client.aclose()


def test_initially_dismissed_review_has_no_invented_approval() -> None:
    row = github.review(
        {
            "id": 7,
            "state": "DISMISSED",
            "submitted_at": "2026-01-02T00:00:00Z",
            "user": {"login": "robot[bot]", "type": "Bot"},
        },
        "team/repo",
        1,
    )
    assert row["approved_at"] is None and row["original_state"] is None
    assert row["reviewer_type"] == "Bot"
    event = github.transition(
        {
            "id": 8,
            "event": "review_dismissed",
            "created_at": "2026-01-03T00:00:00Z",
            "actor": None,
            "dismissed_review": {
                "review_id": "7",
                "state": "approved",
                "dismissal_message": "do not retain this",
            },
        },
        "team/repo",
        1,
    )
    assert event and event["dismissed_state"] == "APPROVED" and event["dismissed_review_id"] == 7
    assert "dismissal_message" not in event


@pytest.mark.parametrize("url", ["javascript:alert(1)", "https://github.com/other/repo/pull/2"])
def test_explicit_references_never_follow_foreign_or_arbitrary_urls(url: str) -> None:
    value: dict[str, Any] = {
        "event": "cross-referenced",
        "created_at": "2026-01-03T00:00:00Z",
        "source": {"type": "issue", "issue": {"number": 2, "pull_request": {}, "html_url": url}},
    }
    assert github.issue_reference(value, "team/repo") == {"outside_repository": True}


def test_open_pr_test_merge_sha_is_not_actual_merge_evidence() -> None:
    from test_pipeline_integration import pr

    value = pr(1)
    value["merge_commit_sha"] = "b" * 40
    assert github.pull_request(value, "team/repo")["merge_commit_sha"] is None
    with pytest.raises(ValueError):
        github.commit_file({"filename": "bad", "status": "added", "additions": True})
