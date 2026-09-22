from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import Field

from forge.api.v1.analytics import End, PageSize, Start
from forge.api.v1.identity import Current, Cursor, Input, csrf
from forge.domain.delivery import Classification
from forge.services.delivery import DeliveryService

router = APIRouter()
Workflow = Annotated[int | None, Query(gt=0, le=9223372036854775807)]
Name = Annotated[str | None, Query(min_length=1, max_length=255)]


def delivery(request: Request) -> DeliveryService:
    result: DeliveryService = request.app.state.delivery_service
    return result


class ClassificationInput(Input):
    environment: str = Field(min_length=1, max_length=255)
    classification: Literal["production", "nonproduction"] | None


@router.get("/organizations/{organization}/metrics/ci")
async def ci_metrics(
    organization: UUID,
    request: Request,
    actor: Current,
    repository: UUID | None = None,
    workflow: Workflow = None,
    branch: Name = None,
    from_time: Start = None,
    to_time: End = None,
) -> dict[str, Any]:
    return await delivery(request).ci_metrics(
        actor, organization, repository, workflow, branch, from_time, to_time
    )


@router.get("/organizations/{organization}/workflow-runs")
async def runs(
    organization: UUID,
    request: Request,
    actor: Current,
    repository: UUID | None = None,
    workflow: Workflow = None,
    branch: Name = None,
    from_time: Start = None,
    to_time: End = None,
    cohort: Literal["activity", "completed"] = "activity",
    outcome: Literal["all", "success", "failure", "other"] = "all",
    metric: Literal["duration", "queue"] | None = None,
    eligibility: Literal["eligible", "excluded", "all"] | None = None,
    limit: PageSize = 30,
    cursor: Cursor = None,
) -> dict[str, Any]:
    return await delivery(request).runs(
        actor,
        organization,
        repository,
        workflow,
        branch,
        from_time,
        to_time,
        cohort,
        outcome,
        metric,
        eligibility,
        limit,
        cursor,
    )


@router.get("/organizations/{organization}/workflow-runs/{identifier}")
async def run_detail(
    organization: UUID,
    identifier: UUID,
    request: Request,
    actor: Current,
) -> dict[str, Any]:
    return await delivery(request).detail(actor, organization, identifier, "run")


@router.get("/organizations/{organization}/workflow-runs/{identifier}/{kind}")
async def run_children(
    organization: UUID,
    identifier: UUID,
    kind: Literal["jobs", "pull-requests", "commits"],
    request: Request,
    actor: Current,
    limit: PageSize = 30,
    cursor: Cursor = None,
) -> dict[str, Any]:
    return await delivery(request).children(
        actor, organization, identifier, "run", kind, limit, cursor
    )


@router.get("/organizations/{organization}/metrics/deployments")
async def deployment_metrics(
    organization: UUID,
    request: Request,
    actor: Current,
    repository: UUID | None = None,
    environment: Name = None,
    classification: Classification = "production",
    from_time: Start = None,
    to_time: End = None,
) -> dict[str, Any]:
    return await delivery(request).deployment_metrics(
        actor, organization, repository, environment, classification, from_time, to_time
    )


@router.get("/organizations/{organization}/deployments")
async def deployments(
    organization: UUID,
    request: Request,
    actor: Current,
    repository: UUID | None = None,
    environment: Name = None,
    classification: Classification = "production",
    from_time: Start = None,
    to_time: End = None,
    cohort: Literal["created", "success"] = "created",
    eligibility: Literal["all", "eligible", "excluded"] = "all",
    limit: PageSize = 30,
    cursor: Cursor = None,
) -> dict[str, Any]:
    return await delivery(request).deployments(
        actor,
        organization,
        repository,
        environment,
        classification,
        from_time,
        to_time,
        cohort,
        eligibility,
        limit,
        cursor,
    )


@router.get("/organizations/{organization}/deployments/{identifier}")
async def deployment_detail(
    organization: UUID,
    identifier: UUID,
    request: Request,
    actor: Current,
) -> dict[str, Any]:
    return await delivery(request).detail(actor, organization, identifier, "deployment")


@router.get("/organizations/{organization}/deployments/{identifier}/{kind}")
async def deployment_children(
    organization: UUID,
    identifier: UUID,
    kind: Literal["statuses", "commits"],
    request: Request,
    actor: Current,
    limit: PageSize = 30,
    cursor: Cursor = None,
) -> dict[str, Any]:
    return await delivery(request).children(
        actor, organization, identifier, "deployment", kind, limit, cursor
    )


@router.get("/organizations/{organization}/repositories/{repository}/environments")
async def environments(
    organization: UUID,
    repository: UUID,
    request: Request,
    actor: Current,
) -> dict[str, Any]:
    return await delivery(request).environments(actor, organization, repository)


@router.put(
    "/organizations/{organization}/repositories/{repository}/environments/classification",
    dependencies=[Depends(csrf)],
)
async def classification(
    organization: UUID,
    repository: UUID,
    request: Request,
    actor: Current,
    body: ClassificationInput,
) -> dict[str, Any]:
    return await delivery(request).classify(
        actor, organization, repository, body.environment, body.classification
    )
