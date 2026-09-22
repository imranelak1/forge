from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Query, Request

from forge.api.v1.identity import Current, Cursor
from forge.domain.analytics import Metric
from forge.services.analytics import AnalyticsService

router = APIRouter()
Author = Annotated[str | None, Query(min_length=1, max_length=100)]
Start = Annotated[datetime | None, Query(alias="from")]
End = Annotated[datetime | None, Query(alias="to")]
PageSize = Annotated[int, Query(ge=1, le=100)]


def analytics(request: Request) -> AnalyticsService:
    result: AnalyticsService = request.app.state.analytics_service
    return result


@router.get("/organizations/{organization}/metrics/pull-requests")
async def metrics(
    organization: UUID,
    request: Request,
    actor: Current,
    repository: UUID | None = None,
    author: Author = None,
    from_time: Start = None,
    to_time: End = None,
) -> dict[str, Any]:
    return await analytics(request).metrics(
        actor, organization, repository, author, from_time, to_time
    )


@router.get("/organizations/{organization}/pull-requests")
async def pull_requests(
    organization: UUID,
    request: Request,
    actor: Current,
    repository: UUID | None = None,
    author: Author = None,
    from_time: Start = None,
    to_time: End = None,
    state: Literal["all", "open", "closed", "merged"] = "all",
    cohort: Literal["activity", "merged"] = "activity",
    metric: Metric | None = None,
    eligibility: Literal["eligible", "excluded", "all"] | None = None,
    limit: PageSize = 30,
    cursor: Cursor = None,
) -> dict[str, Any]:
    return await analytics(request).pull_requests(
        actor,
        organization,
        repository,
        author,
        from_time,
        to_time,
        state,
        cohort,
        metric,
        eligibility,
        limit,
        cursor,
    )


@router.get("/organizations/{organization}/pull-requests/{identifier}")
async def pull_request(
    organization: UUID, identifier: UUID, request: Request, actor: Current
) -> dict[str, Any]:
    return await analytics(request).pull_request(actor, organization, identifier)


@router.get("/organizations/{organization}/pull-requests/{identifier}/{kind}")
async def pull_request_evidence(
    organization: UUID,
    identifier: UUID,
    kind: Literal["reviews", "transitions", "commits", "issues"],
    request: Request,
    actor: Current,
    limit: PageSize = 30,
    cursor: Cursor = None,
) -> dict[str, Any]:
    return await analytics(request).evidence(
        actor, organization, "pull_request", identifier, kind, limit, cursor
    )


@router.get("/organizations/{organization}/commits")
async def commits(
    organization: UUID,
    request: Request,
    actor: Current,
    repository: UUID | None = None,
    author: Author = None,
    from_time: Start = None,
    to_time: End = None,
    limit: PageSize = 30,
    cursor: Cursor = None,
) -> dict[str, Any]:
    return await analytics(request).commits(
        actor, organization, repository, author, from_time, to_time, limit, cursor
    )


@router.get("/organizations/{organization}/commits/{identifier}")
async def commit(
    organization: UUID, identifier: UUID, request: Request, actor: Current
) -> dict[str, Any]:
    return await analytics(request).commit(actor, organization, identifier)


@router.get("/organizations/{organization}/commits/{identifier}/{kind}")
async def commit_evidence(
    organization: UUID,
    identifier: UUID,
    kind: Literal["files", "pull-requests"],
    request: Request,
    actor: Current,
    limit: PageSize = 30,
    cursor: Cursor = None,
) -> dict[str, Any]:
    return await analytics(request).evidence(
        actor, organization, "commit", identifier, kind, limit, cursor
    )


@router.get("/organizations/{organization}/repositories/{repository}/issues")
async def issues(
    organization: UUID,
    repository: UUID,
    request: Request,
    actor: Current,
    author: Author = None,
    from_time: Start = None,
    to_time: End = None,
    state: Literal["all", "open", "closed"] = "all",
    limit: PageSize = 30,
    cursor: Cursor = None,
) -> dict[str, Any]:
    return await analytics(request).issues(
        actor, organization, repository, author, from_time, to_time, state, limit, cursor
    )


@router.get("/organizations/{organization}/issues/{identifier}")
async def issue(
    organization: UUID, identifier: UUID, request: Request, actor: Current
) -> dict[str, Any]:
    return await analytics(request).issue(actor, organization, identifier)


@router.get("/organizations/{organization}/issues/{identifier}/pull-requests")
async def issue_evidence(
    organization: UUID,
    identifier: UUID,
    request: Request,
    actor: Current,
    limit: PageSize = 30,
    cursor: Cursor = None,
) -> dict[str, Any]:
    return await analytics(request).evidence(
        actor, organization, "issue", identifier, "pull-requests", limit, cursor
    )
