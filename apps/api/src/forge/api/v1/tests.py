import asyncio
from typing import Annotated, Any, Self
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import Field, model_validator

from forge.api.v1.identity import Current, Cursor, Input, Limit, csrf
from forge.domain.identity import DomainError
from forge.domain.tests import MAX_REPORT_BYTES, invalid_token
from forge.services.tests import TestService

router = APIRouter()


def tests(request: Request) -> TestService:
    result: TestService = request.app.state.test_service
    return result


class TokenInput(Input):
    name: str = Field(min_length=1, max_length=100)
    expires_in_days: int = Field(default=30, ge=1, le=90, strict=True)


class PolicyInput(Input):
    window_days: int | None = Field(default=None, ge=2, le=90, strict=True)
    min_executions: int | None = Field(default=None, ge=2, le=1000, strict=True)
    failure_rate_low: float | None = Field(default=None, gt=0, lt=1, strict=True)
    failure_rate_high: float | None = Field(default=None, gt=0, lt=1, strict=True)
    min_transitions: int | None = Field(default=None, ge=1, le=100, strict=True)
    excluded_branches: list[Annotated[str, Field(min_length=1, max_length=255)]] | None = Field(
        default=None, max_length=50
    )

    @model_validator(mode="after")
    def no_null_changes(self) -> Self:
        if not self.model_fields_set or any(
            getattr(self, key) is None for key in self.model_fields_set
        ):
            raise ValueError("Supply at least one non-null policy field.")
        return self


@router.get("/organizations/{organization}/repositories/{repository}/service-tokens")
async def list_tokens(
    organization: UUID,
    repository: UUID,
    request: Request,
    actor: Current,
    limit: Limit = 30,
    cursor: Cursor = None,
) -> dict[str, Any]:
    return await tests(request).tokens(actor, organization, repository, limit, cursor)


@router.post(
    "/organizations/{organization}/repositories/{repository}/service-tokens",
    status_code=201,
    dependencies=[Depends(csrf)],
)
async def create_token(
    organization: UUID, repository: UUID, request: Request, actor: Current, body: TokenInput
) -> dict[str, Any]:
    return await tests(request).create_token(
        actor, organization, repository, body.name, body.expires_in_days
    )


@router.delete(
    "/organizations/{organization}/service-tokens/{identifier}",
    status_code=204,
    dependencies=[Depends(csrf)],
)
async def revoke_token(
    organization: UUID, identifier: UUID, request: Request, actor: Current
) -> Response:
    await tests(request).revoke_token(actor, organization, identifier)
    return Response(status_code=204)


@router.get("/organizations/{organization}/repositories/{repository}/test-policy")
async def get_policy(
    organization: UUID, repository: UUID, request: Request, actor: Current
) -> dict[str, Any]:
    return await tests(request).policy(actor, organization, repository)


@router.patch(
    "/organizations/{organization}/repositories/{repository}/test-policy",
    dependencies=[Depends(csrf)],
)
async def patch_policy(
    organization: UUID, repository: UUID, request: Request, actor: Current, body: PolicyInput
) -> dict[str, Any]:
    return await tests(request).policy(
        actor, organization, repository, body.model_dump(exclude_unset=True)
    )


@router.post(
    "/organizations/{organization}/repositories/{repository}/test-reports", status_code=202
)
async def upload(
    organization: UUID,
    repository: UUID,
    request: Request,
    workflow_run_id: Annotated[int, Query(gt=0, le=9223372036854775807)],
    run_attempt: Annotated[int, Query(gt=0, le=2147483647)],
    report_key: Annotated[str, Query(min_length=1, max_length=200)],
    shard: Annotated[str, Query(min_length=1, max_length=200)] = "default",
    framework: Annotated[str, Query(min_length=1, max_length=80)] = "junit",
    environment: Annotated[str | None, Query(min_length=1, max_length=255)] = None,
    commit_sha: Annotated[str | None, Query(pattern=r"^[a-f0-9]{40}$")] = None,
    supersedes: UUID | None = None,
) -> dict[str, Any]:
    if len(request.headers.getlist("authorization")) != 1:
        raise invalid_token()
    service = tests(request)
    authenticated = await service.authenticate_upload(
        organization, repository, request.headers.get("authorization")
    )
    media = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if (
        media not in {"application/xml", "text/xml"}
        or request.headers.get("content-encoding", "identity") != "identity"
    ):
        raise DomainError(
            415, "unsupported_report_format", "Upload uncompressed JUnit XML directly."
        )
    payload = bytearray()
    try:
        async with asyncio.timeout(15):
            async for chunk in request.stream():
                if len(payload) + len(chunk) > MAX_REPORT_BYTES:
                    raise DomainError(413, "report_too_large", "Reports must not exceed 10 MiB.")
                payload.extend(chunk)
    except TimeoutError as exc:
        raise DomainError(
            408, "upload_timeout", "The upload did not finish within 15 seconds."
        ) from exc
    if not payload:
        raise DomainError(422, "empty_report", "Upload a nonempty JUnit XML report.")
    return await service.upload(
        organization,
        repository,
        authenticated,
        bytes(payload),
        {
            "workflow_run_id": workflow_run_id,
            "run_attempt": run_attempt,
            "report_key": report_key,
            "shard": shard,
            "framework": framework,
            "environment": environment,
            "commit_sha": commit_sha,
            "supersedes": supersedes,
        },
    )
