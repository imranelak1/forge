"""Bounded provider evidence pages; checkpoints commit with their fenced job."""

import json
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncConnection

from forge.domain import github as normalize
from forge.integrations.github import GitHubApp, GitHubFailure
from forge.repositories.enrichment import PREFIXES
from forge.repositories.pipeline import Lease, LostLease, PipelineRepository, Work


@dataclass
class EvidencePage:
    stage: str
    page: int
    records: list[dict[str, Any]] = field(default_factory=list)
    done: bool = True
    issues: bool = False
    data: dict[str, Any] = field(default_factory=dict)


class EnrichmentWorker:
    def __init__(self, repository: PipelineRepository, provider: GitHubApp) -> None:
        self.repository = repository
        self.provider = provider

    async def fetch(self, work: Work) -> EvidencePage:
        assert work.repository and work.subject
        checkpoint = work.job["payload"]
        stage, number = checkpoint["stage"], checkpoint["page"]
        if type(number) is not int or not 1 <= number <= 100:
            raise GitHubFailure("capacity_exceeded")
        repo, subject = work.repository, work.subject
        token, issues = await self.provider.enrichment_credentials(
            work.integration["installation_id"]
        )
        result = EvidencePage(stage, number, issues=issues)
        args = token, repo["owner"], repo["name"]
        full_name = repo["full_name"]
        if stage in {"scan_pull_requests", "scan_commits"}:
            return result
        if stage == "details":
            value = await self.provider.pull_request(*args, subject["number"])
            row = normalize.pull_request(value, full_name)
            if row["number"] != subject["number"] or row["updated_at"] < subject["updated_at"]:
                raise GitHubFailure("source_changed", retryable=True)
            result.records = [row]
        elif stage == "reviews":
            values = await self.provider.reviews(*args, subject["number"], number)
            result.records = [
                normalize.review(value, full_name, subject["number"]) for value in values
            ]
            result.done = len(values) < 100
        elif stage in {"timeline", "issue_timeline"}:
            if stage == "issue_timeline" and not issues:
                result.data["unavailable"] = True
                return result
            values = await self.provider.timeline(*args, subject["number"], number)
            references = []
            for value in values:
                if stage == "timeline":
                    transition = normalize.transition(value, full_name, subject["number"])
                    if transition:
                        result.records.append(transition)
                reference = normalize.issue_reference(value, full_name) if issues else None
                if reference:
                    if not reference.get("outside_repository") and not reference["is_pr"]:
                        reference["issue"] = normalize.issue(value["source"]["issue"], full_name)
                    references.append(reference)
            result.data["references"] = references
            result.done = len(values) < 100
        elif stage == "members":
            values = await self.provider.pull_request_commits(*args, subject["number"], number)
            result.records = [normalize.commit(value, full_name) for value in values]
            result.done = len(values) < 100 or number == 3
            total = subject["provider_commit_count"]
            if number == 3 and ((total is None and len(values) >= 50) or (total or 0) > 250):
                result.data["partial"] = "provider_commit_limit"
        elif stage in {"files", "merge"}:
            identifier = subject["sha"] if stage == "files" else subject["merge_commit_sha"]
            if not identifier:
                result.data["unavailable"] = True
                return result
            value = await self.provider.commit_details(*args, identifier, number)
            row = normalize.commit(value, full_name)
            if row["sha"] != identifier:
                raise GitHubFailure("invalid_response")
            result.data["commit"] = row
            stats = normalize.object_value(value.get("stats"))
            result.data["stats"] = {
                key: normalize.count(stats.get(key)) for key in ("additions", "deletions", "total")
            }
            result.records = [normalize.commit_file(item) for item in value["files"]]
            result.done = len(result.records) < 100 or number == 30
            if number == 30 and len(result.records) == 100:
                result.data["partial"] = "provider_file_limit"
        elif stage == "issues":
            if not issues:
                result.data["unavailable"] = True
                return result
            values = await self.provider.issues(*args, number, checkpoint["since"])
            result.records = [
                normalize.issue(value, full_name) for value in values if "pull_request" not in value
            ]
            result.done = len(values) < 100
        elif stage == "issue_details":
            if not issues:
                result.data["unavailable"] = True
                return result
            value = await self.provider.issue(*args, subject["number"])
            row = normalize.issue(value, full_name)
            if row["number"] != subject["number"] or row["updated_at"] < subject["updated_at"]:
                raise GitHubFailure("source_changed", retryable=True)
            result.records = [row]
        else:
            raise GitHubFailure("invalid_checkpoint")
        if not result.done and number == 100:
            result.done = True
            result.data["partial"] = "provider_page_limit"
        return result

    async def persist(
        self,
        connection: AsyncConnection,
        lease: Lease,
        work: Work,
        result: EvidencePage,
    ) -> str:
        assert work.repository and work.subject
        repo = self.repository
        org, integration, source = (
            lease.organization_id,
            work.integration["id"],
            work.repository["id"],
        )
        subject = work.subject
        checkpoint = dict(work.job["payload"])
        kind, identifier = checkpoint["kind"], subject["id"]
        if (
            kind in {"pull_request", "issue"}
            and checkpoint["revision"] != subject["updated_at"].isoformat()
        ):
            raise LostLease
        stage = result.stage
        next_stage = stage
        finished = False
        partial = result.data.get("partial")
        if partial:
            checkpoint[f"{stage}_partial"] = partial
        if stage in {"scan_pull_requests", "scan_commits"}:
            table = "pull_requests" if stage == "scan_pull_requests" else "commits"
            child_kind = "pull_request" if stage == "scan_pull_requests" else "commit"
            rows = await repo.many(
                connection,
                f"""SELECT * FROM forge.{table}
                WHERE organization_id=:org AND repository_id=:repo AND id>CAST(:after AS uuid)
                ORDER BY id LIMIT 100""",
                org=org,
                repo=source,
                after=checkpoint.get("after", "00000000-0000-0000-0000-000000000000"),
            )
            for row in rows:
                await repo.queue_enrichment(
                    connection, org, integration, source, child_kind, row, force=True
                )
            if len(rows) == 100:
                checkpoint["after"] = str(rows[-1]["id"])
                result.done = False
            else:
                checkpoint.pop("after", None)
                next_stage = "scan_commits" if stage == "scan_pull_requests" else "issues"
        elif stage == "details":
            current = await repo.upsert_pull_request(
                connection, org, integration, source, result.records[0], schedule=False
            )
            checkpoint["revision"] = current["updated_at"].isoformat()
            await repo.upsert_transition(
                connection,
                org,
                source,
                identifier,
                {
                    "provider_id": None,
                    "source_key": "opened",
                    "kind": "opened",
                    "occurred_at": current["opened_at"],
                    "actor_login": current["author_login"],
                    "actor_type": current["author_type"],
                    "html_url": current["html_url"],
                },
            )
            await repo.coverage(
                connection,
                org,
                "pull_request",
                identifier,
                "issues",
                "pending" if result.issues else "unavailable",
                None if result.issues else "issues_permission_required",
            )
            next_stage = "reviews"
        elif stage == "reviews":
            for row in result.records:
                await repo.upsert_review(connection, org, source, identifier, row)
            await repo.coverage(
                connection,
                org,
                kind,
                identifier,
                "reviews",
                "partial" if partial or not result.done else "complete",
                partial,
            )
            if result.done:
                next_stage = "timeline"
        elif stage in {"timeline", "issue_timeline"}:
            for row in result.records:
                await repo.upsert_transition(connection, org, source, identifier, row)
            for reference in result.data.get("references", []):
                if reference.get("outside_repository"):
                    checkpoint["links_partial"] = "outside_repository_reference"
                    continue
                if stage == "timeline" and not reference["is_pr"]:
                    issue = await repo.upsert_issue(
                        connection, org, integration, source, reference["issue"]
                    )
                    await repo.link_issue(
                        connection, org, source, issue["id"], identifier, reference
                    )
                elif stage == "issue_timeline" and reference["is_pr"]:
                    pr = await repo.one(
                        connection,
                        """SELECT id FROM forge.pull_requests
                        WHERE organization_id=:org AND repository_id=:repo AND number=:number""",
                        org=org,
                        repo=source,
                        number=reference["number"],
                    )
                    if pr:
                        await repo.link_issue(
                            connection, org, source, identifier, pr["id"], reference
                        )
                    else:
                        checkpoint["links_partial"] = "referenced_pull_request_not_imported"
            if stage == "timeline":
                await repo.coverage(
                    connection,
                    org,
                    kind,
                    identifier,
                    "transitions",
                    "partial" if partial or not result.done else "complete",
                    partial,
                )
            prefix = "issues" if stage == "timeline" else "links"
            issue_error = partial or checkpoint.get("links_partial")
            status = "partial" if issue_error or not result.done else "complete"
            if not result.issues:
                status, issue_error = "unavailable", "issues_permission_required"
            await repo.coverage(connection, org, kind, identifier, prefix, status, issue_error)
            if result.done:
                if stage == "timeline":
                    next_stage = "members"
                else:
                    finished = True
        elif stage == "members":
            if result.page == 1:
                await repo.execute(
                    connection,
                    """DELETE FROM forge.pull_request_commits
                    WHERE organization_id=:org AND pull_request_id=:pr AND relationship='head'""",
                    org=org,
                    pr=identifier,
                )
            for row in result.records:
                commit = await repo.upsert_commit(connection, org, integration, source, row)
                await repo.link_commit(
                    connection, org, source, identifier, commit["id"], "head", row["html_url"]
                )
            await repo.coverage(connection, org, kind, identifier, "commits", "partial", partial)
            if result.done:
                next_stage = "merge"
        elif stage == "merge":
            if not result.data.get("unavailable"):
                row = result.data["commit"]
                commit = await repo.upsert_commit(connection, org, integration, source, row)
                await repo.link_commit(
                    connection, org, source, identifier, commit["id"], "merge", row["html_url"]
                )
            error = checkpoint.get("members_partial")
            if subject["merged_at"] and not subject["merge_commit_sha"]:
                error = error or "merge_commit_unavailable"
            await repo.coverage(
                connection,
                org,
                kind,
                identifier,
                "commits",
                "partial" if error else "complete",
                error,
            )
            finished = True
        elif stage == "files":
            stats = result.data["stats"]
            await repo.execute(
                connection,
                """UPDATE forge.commits
                SET additions=:additions,deletions=:deletions,total_changes=:total
                WHERE organization_id=:org AND id=:id""",
                org=org,
                id=identifier,
                **stats,
            )
            for row in result.records:
                await repo.upsert_file(connection, org, source, identifier, row)
            await repo.coverage(
                connection,
                org,
                kind,
                identifier,
                "files",
                "partial" if partial or not result.done else "complete",
                partial,
            )
            finished = result.done
        elif stage == "issues":
            for row in result.records:
                issue = await repo.upsert_issue(connection, org, integration, source, row)
                await repo.queue_enrichment(
                    connection, org, integration, source, "issue", issue, force=True
                )
            unavailable = result.data.get("unavailable", False)
            await repo.coverage(
                connection,
                org,
                kind,
                identifier,
                "issues",
                "unavailable"
                if unavailable
                else "partial"
                if partial or not result.done
                else "complete",
                "issues_permission_required" if unavailable else partial,
            )
            if unavailable:
                await repo.execute(
                    connection,
                    """UPDATE forge.pull_requests
                    SET issues_status='unavailable',issues_error='issues_permission_required',
                        issues_synced_at=now()
                    WHERE organization_id=:org AND repository_id=:repo""",
                    org=org,
                    repo=source,
                )
            finished = result.done
        elif stage == "issue_details":
            if result.data.get("unavailable"):
                await repo.coverage(
                    connection,
                    org,
                    kind,
                    identifier,
                    "links",
                    "unavailable",
                    "issues_permission_required",
                )
                finished = True
            else:
                current = await repo.upsert_issue(
                    connection, org, integration, source, result.records[0], schedule=False
                )
                checkpoint["revision"] = current["updated_at"].isoformat()
                next_stage = "issue_timeline"
        checkpoint["stage"] = next_stage
        checkpoint["page"] = 1 if next_stage != stage else result.page + 1
        await repo.execute(
            connection,
            """UPDATE forge.jobs SET payload=CAST(:payload AS jsonb)
            WHERE organization_id=:org AND id=:id""",
            org=org,
            id=lease.id,
            payload=json.dumps(checkpoint),
        )
        await repo.finish_job(
            connection, lease, state="succeeded" if finished else "queued", reset_attempts=True
        )
        return "completed" if finished else "checkpointed"

    async def failure(
        self,
        connection: AsyncConnection,
        org: UUID,
        work: Work,
        code: str,
        retrying: bool,
    ) -> None:
        assert work.subject
        checkpoint = work.job["payload"]
        kind = checkpoint["kind"]
        stage = checkpoint["stage"]
        prefix = {
            "details": "reviews",
            "reviews": "reviews",
            "timeline": "transitions",
            "members": "commits",
            "merge": "commits",
            "files": "files",
            "issues": "issues",
            "issue_details": "links",
            "issue_timeline": "links",
        }.get(stage)
        targets = (prefix,) if prefix else PREFIXES[kind]
        for target in targets:
            await self.repository.coverage(
                connection,
                org,
                kind,
                work.subject["id"],
                target,
                "partial" if retrying or checkpoint["page"] > 1 else "failed",
                code,
            )
