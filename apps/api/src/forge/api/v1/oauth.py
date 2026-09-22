from typing import Any, Literal

from fastapi import APIRouter, Depends, Request, Response
from pydantic import Field
from starlette.responses import RedirectResponse

from forge.api.v1.identity import (
    Current,
    Input,
    client_ip,
    csrf,
    service,
    session_response,
    set_cookie,
)
from forge.integrations.oauth import PROVIDERS, Provider
from forge.services.oauth import OAUTH_SECONDS, OAuthService

router = APIRouter()


class StartInput(Input):
    intent: Literal["login", "link"] = "login"
    return_to: str = Field(default="/app", max_length=2048)


def oauth(request: Request) -> OAuthService:
    result: OAuthService = request.app.state.oauth_service
    return result


@router.get("/auth/providers")
async def providers(request: Request) -> dict[str, Any]:
    return {
        "providers": [
            {"id": item, "enabled": oauth(request).provider.enabled(item)} for item in PROVIDERS
        ]
    }


@router.post("/auth/oauth/{provider}/start", dependencies=[Depends(csrf)])
async def start(
    provider: Provider, body: StartInput, request: Request, response: Response
) -> dict[str, str]:
    identity = service(request)
    actor = (
        await identity.authenticate(request.cookies.get("forge_access"))
        if body.intent == "link"
        else None
    )
    await identity.rate_limit("oauth_start", client_ip(request))
    result = await oauth(request).start(provider, body.intent, body.return_to, actor)
    set_cookie(
        request,
        response,
        "forge_oauth",
        result.browser_binding,
        lifetime=OAUTH_SECONDS,
        path="/api/v1/auth/oauth",
    )
    return {"authorization_url": result.authorization_url}


@router.get("/auth/oauth/{provider}/callback")
async def callback(provider: Provider, request: Request) -> RedirectResponse:
    query = request.query_params
    # Ambiguous or oversized provider replies never reach an exchange endpoint.
    valid = all(len(query.getlist(key)) <= 1 for key in ("state", "code", "error"))
    result = await oauth(request).callback(
        provider,
        query.get("state", "") if valid else "",
        request.cookies.get("forge_oauth"),
        query.get("code"),
        query.get("error"),
        request.cookies.get("forge_access"),
        issuer=query.get("iss") if len(query.getlist("iss")) <= 1 else "",
    )
    response = RedirectResponse(result.location, status_code=303)
    if result.session:
        session_response(request, response, result.session)
    response.delete_cookie(
        "forge_oauth",
        path="/api/v1/auth/oauth",
        httponly=True,
        samesite="lax",
        secure=request.app.state.settings.public_origin.startswith("https://"),
    )
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@router.get("/auth/connections")
async def connections(request: Request, actor: Current) -> dict[str, Any]:
    return await oauth(request).connections(actor)
