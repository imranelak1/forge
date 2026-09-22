from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from pydantic import Field
from starlette.responses import RedirectResponse

from forge.api.v1.identity import (
    Current,
    Cursor,
    Input,
    Limit,
    client_ip,
    csrf,
    service,
    set_cookie,
)
from forge.services.github import AUTHORIZATION_SECONDS, GitHubService

router = APIRouter()


def github(request: Request) -> GitHubService:
    result: GitHubService = request.app.state.github_service
    return result


class ConnectionInput(Input):
    authorization_id: UUID
    installation_id: int = Field(gt=0, le=9223372036854775807, strict=True)


class SelectionChange(Input):
    id: UUID
    selected: bool = Field(strict=True)


class SelectionInput(Input):
    changes: list[SelectionChange] = Field(min_length=1, max_length=100)


@router.get("/organizations/{organization}/integrations/github")
async def status(organization: UUID, request: Request, actor: Current) -> dict[str, Any]:
    return await github(request).status(actor, organization)


@router.post(
    "/organizations/{organization}/integrations/github/authorize", dependencies=[Depends(csrf)]
)
async def authorize(
    organization: UUID, request: Request, response: Response, actor: Current
) -> dict[str, str]:
    await service(request).rate_limit("github_authorize", client_ip(request), str(actor.user_id))
    url, binding = await github(request).authorize(actor, organization)
    set_cookie(
        request,
        response,
        "forge_github_app",
        binding,
        lifetime=AUTHORIZATION_SECONDS,
        path="/api/v1/integrations/github",
    )
    return {"authorization_url": url}


@router.get("/integrations/github/callback")
async def callback(request: Request) -> RedirectResponse:
    query = request.query_params
    valid = all(len(query.getlist(key)) <= 1 for key in ("state", "code", "error"))
    target = await github(request).callback(
        query.get("state", "") if valid else "",
        request.cookies.get("forge_github_app"),
        query.get("code"),
        query.get("error"),
        request.cookies.get("forge_access"),
        query.get("iss") if len(query.getlist("iss")) <= 1 else "",
    )
    response = RedirectResponse(target, status_code=303)
    response.delete_cookie(
        "forge_github_app",
        path="/api/v1/integrations/github",
        httponly=True,
        samesite="lax",
        secure=request.app.state.settings.public_origin.startswith("https://"),
    )
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@router.get(
    "/organizations/{organization}/integrations/github/authorizations/{authorization}/installations"
)
async def installations(
    organization: UUID, authorization: UUID, request: Request, actor: Current
) -> dict[str, Any]:
    return await github(request).installations(actor, organization, authorization)


@router.post(
    "/organizations/{organization}/integrations/github/connections",
    status_code=201,
    dependencies=[Depends(csrf)],
)
async def bind(
    organization: UUID, body: ConnectionInput, request: Request, actor: Current
) -> dict[str, Any]:
    await service(request).rate_limit("github_bind", client_ip(request), str(actor.user_id))
    return await github(request).bind(
        actor, organization, body.authorization_id, body.installation_id
    )


@router.post(
    "/organizations/{organization}/integrations/github/connections/{connection}/refresh",
    status_code=202,
    dependencies=[Depends(csrf)],
)
async def refresh(
    organization: UUID, connection: UUID, request: Request, actor: Current
) -> dict[str, Any]:
    await service(request).rate_limit("github_refresh", client_ip(request), str(actor.user_id))
    return await github(request).refresh(actor, organization, connection)


@router.delete(
    "/organizations/{organization}/integrations/github/connections/{connection}",
    status_code=204,
    dependencies=[Depends(csrf)],
)
async def disconnect(
    organization: UUID, connection: UUID, request: Request, actor: Current
) -> None:
    await github(request).disconnect(actor, organization, connection)


@router.get(
    "/organizations/{organization}/integrations/github/connections/{connection}/repositories"
)
async def catalog(
    organization: UUID,
    connection: UUID,
    request: Request,
    actor: Current,
    limit: Limit = 50,
    cursor: Cursor = None,
) -> dict[str, Any]:
    return await github(request).repositories(actor, organization, connection, limit, cursor)


@router.post(
    "/organizations/{organization}/integrations/github/connections/{connection}/selection",
    dependencies=[Depends(csrf)],
)
async def selection(
    organization: UUID, connection: UUID, body: SelectionInput, request: Request, actor: Current
) -> dict[str, int]:
    return await github(request).selection(
        actor, organization, connection, [(item.id, item.selected) for item in body.changes]
    )


@router.get("/organizations/{organization}/repositories")
async def repositories(
    organization: UUID, request: Request, actor: Current, limit: Limit = 50, cursor: Cursor = None
) -> dict[str, Any]:
    return await github(request).repositories(actor, organization, None, limit, cursor)


@router.get("/organizations/{organization}/repositories/{repository}/sync-runs")
async def sync_runs(
    organization: UUID,
    repository: UUID,
    request: Request,
    actor: Current,
    limit: Limit = 50,
    cursor: Cursor = None,
) -> dict[str, Any]:
    return await github(request).sync_runs(actor, organization, repository, limit, cursor)


@router.post(
    "/organizations/{organization}/repositories/{repository}/sync",
    status_code=202,
    dependencies=[Depends(csrf)],
)
async def sync(
    organization: UUID, repository: UUID, request: Request, actor: Current
) -> dict[str, Any]:
    await service(request).rate_limit("github_sync", client_ip(request), str(actor.user_id))
    return await github(request).sync(actor, organization, repository)
