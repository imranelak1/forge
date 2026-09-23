"""Authenticated test evidence; CI upload credentials never authorize reads."""

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Query, Request

from forge.api.v1.analytics import End, PageSize, Start
from forge.api.v1.identity import Current, Cursor
from forge.services.test_analytics import TestAnalyticsService

router = APIRouter()
Name = Annotated[str | None, Query(min_length=1, max_length=255)]
Status = Literal["passed", "failed", "error", "skipped"]


def analytics(request: Request) -> TestAnalyticsService:
    result: TestAnalyticsService = request.app.state.test_analytics_service
    return result


@router.get("/organizations/{organization}/metrics/tests")
async def metrics(
    organization: UUID,
    request: Request,
    actor: Current,
    repository: UUID | None = None,
    branch: Name = None,
    environment: Name = None,
    from_time: Start = None,
    to_time: End = None,
) -> dict[str, Any]:
    return await analytics(request).test_metrics(
        actor, organization, repository, branch, environment, from_time, to_time
    )


@router.get("/organizations/{organization}/test-runs")
async def reports(
    organization: UUID,
    request: Request,
    actor: Current,
    repository: UUID | None = None,
    branch: Name = None,
    environment: Name = None,
    from_time: Start = None,
    to_time: End = None,
    status: Literal["queued", "processing", "completed", "failed"] | None = None,
    limit: PageSize = 30,
    cursor: Cursor = None,
) -> dict[str, Any]:
    return await analytics(request).reports(
        actor,
        organization,
        repository,
        branch,
        environment,
        from_time,
        to_time,
        status,
        limit,
        cursor,
    )


@router.get("/organizations/{organization}/test-runs/{identifier}")
async def report(
    organization: UUID,
    identifier: UUID,
    request: Request,
    actor: Current,
) -> dict[str, Any]:
    return await analytics(request).report(actor, organization, identifier)


@router.get("/organizations/{organization}/test-runs/{identifier}/{kind}")
async def report_children(
    organization: UUID,
    identifier: UUID,
    kind: Literal["suites", "cases"],
    request: Request,
    actor: Current,
    status: Status | None = None,
    limit: PageSize = 30,
    cursor: Cursor = None,
) -> dict[str, Any]:
    return await analytics(request).children(
        actor,
        organization,
        identifier,
        kind,
        status,
        limit,
        cursor,
    )


@router.get("/organizations/{organization}/tests")
async def candidates(
    organization: UUID,
    request: Request,
    actor: Current,
    repository: UUID | None = None,
    branch: Name = None,
    environment: Name = None,
    to_time: End = None,
    potential_only: bool = True,
    limit: PageSize = 30,
    cursor: Cursor = None,
) -> dict[str, Any]:
    return await analytics(request).candidates(
        actor,
        organization,
        repository,
        branch,
        environment,
        to_time,
        potential_only,
        limit,
        cursor,
    )


@router.get("/organizations/{organization}/tests/{identifier}/history")
async def history(
    organization: UUID,
    identifier: UUID,
    request: Request,
    actor: Current,
    branch: Name = None,
    environment: Name = None,
    from_time: Start = None,
    to_time: End = None,
    limit: PageSize = 30,
    cursor: Cursor = None,
) -> dict[str, Any]:
    return await analytics(request).history(
        actor,
        organization,
        identifier,
        branch,
        environment,
        from_time,
        to_time,
        limit,
        cursor,
    )
