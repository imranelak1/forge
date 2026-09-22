import hmac
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from forge.domain.identity import Actor, DomainError, Role, unauthorized
from forge.security.identity import ACCESS_SECONDS, SESSION_SECONDS, now, opaque_token, token_hash
from forge.services.identity import IdentityService, SessionResult
from forge.services.organizations import OrganizationService

router = APIRouter()


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)


class EmailInput(Input):
    email: EmailStr = Field(max_length=254)

    @field_validator("email", mode="after")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.casefold()


class LoginInput(EmailInput):
    password: str = Field(min_length=1, max_length=128)


class RegisterInput(LoginInput):
    name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Name cannot be blank")
        return value.strip()


class TokenInput(Input):
    token: str = Field(min_length=1, max_length=128)


class ResetInput(TokenInput):
    password: str = Field(min_length=12, max_length=128)


class OrganizationName(Input):
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Name cannot be blank")
        return value.strip()


class OrganizationInput(OrganizationName):
    slug: str = Field(min_length=3, max_length=63, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class RoleInput(Input):
    role: Role


class InvitationInput(EmailInput):
    role: Role = Role.MEMBER


def service(request: Request) -> IdentityService:
    result: IdentityService = request.app.state.identity_service
    return result


def organizations(request: Request) -> OrganizationService:
    result: OrganizationService = request.app.state.organization_service
    return result


async def current_actor(request: Request) -> Actor:
    return await service(request).authenticate(request.cookies.get("forge_access"))


async def csrf(request: Request) -> None:
    identity = service(request)
    if request.headers.get("origin") != request.app.state.settings.public_origin:
        raise DomainError(403, "origin_failed", "The request origin is not allowed.")
    header = request.headers.get("x-csrf-token", "")
    cookie = request.cookies.get("forge_csrf", "")
    if (
        not header
        or len(header) > 128
        or len(cookie) > 128
        or not header.isascii()
        or not cookie.isascii()
        or not hmac.compare_digest(header, cookie)
    ):
        raise DomainError(403, "csrf_failed", "Refresh the page and try again.")
    actor = await identity.csrf_actor(
        request.cookies.get("forge_access"), request.cookies.get("forge_refresh")
    )
    if actor:
        valid = identity.tokens.csrf_matches(header, actor.csrf_hash)
    else:
        if not request.url.path.startswith("/api/v1/auth/"):
            # Expired access must trigger the client's refresh flow on protected mutations.
            raise unauthorized()
        try:
            data = identity.tokens.decode(request.cookies.get("forge_preauth", ""), "preauth")
            valid = hmac.compare_digest(token_hash(header), data.get("csrf_hash", ""))
        except DomainError:
            valid = False
    if not valid:
        raise DomainError(403, "csrf_failed", "Refresh the page and try again.")


def set_cookie(
    request: Request,
    response: Response,
    name: str,
    value: str,
    *,
    lifetime: int,
    http_only: bool = True,
    path: str = "/api/v1",
) -> None:
    response.set_cookie(
        name,
        value,
        max_age=lifetime,
        httponly=http_only,
        secure=request.app.state.settings.public_origin.startswith("https://"),
        samesite="lax",
        path=path,
    )


def clear_cookies(request: Request, response: Response) -> None:
    for name, path in (
        ("forge_access", "/api/v1"),
        ("forge_refresh", "/api/v1/auth"),
        ("forge_csrf", "/"),
        ("forge_preauth", "/api/v1"),
    ):
        response.delete_cookie(
            name,
            path=path,
            secure=request.app.state.settings.public_origin.startswith("https://"),
            httponly=name != "forge_csrf",
            samesite="lax",
        )


def session_response(request: Request, response: Response, result: SessionResult) -> dict[str, Any]:
    lifetime = max(0, min(SESSION_SECONDS, int((result.expires_at - now()).total_seconds())))
    set_cookie(request, response, "forge_access", result.access, lifetime=ACCESS_SECONDS)
    set_cookie(
        request, response, "forge_refresh", result.refresh, lifetime=lifetime, path="/api/v1/auth"
    )
    set_cookie(
        request, response, "forge_csrf", result.csrf, lifetime=lifetime, http_only=False, path="/"
    )
    response.delete_cookie(
        "forge_preauth",
        path="/api/v1",
        httponly=True,
        samesite="lax",
        secure=request.app.state.settings.public_origin.startswith("https://"),
    )
    return {"user": result.actor.user(), "session_id": str(result.actor.session_id)}


def client_ip(request: Request) -> str:
    # ASGI peer is authoritative; proxy trust is deployment-owned.
    return request.client.host if request.client else "unknown"


Limit = Annotated[int, Query(ge=1, le=100)]
Cursor = Annotated[str | None, Query(max_length=2048)]
Current = Annotated[Actor, Depends(current_actor)]


@router.get("/auth/csrf")
async def csrf_token(request: Request, response: Response) -> dict[str, str]:
    identity = service(request)
    actor = await identity.csrf_actor(
        request.cookies.get("forge_access"), request.cookies.get("forge_refresh")
    )
    if actor:
        token = identity.tokens.csrf(actor.session_id)
    else:
        token = opaque_token()
        binding = identity.tokens.encode({"csrf_hash": token_hash(token)}, 900, "preauth")
        set_cookie(request, response, "forge_preauth", binding, lifetime=900)
    set_cookie(
        request,
        response,
        "forge_csrf",
        token,
        lifetime=SESSION_SECONDS if actor else 900,
        http_only=False,
        path="/",
    )
    return {"csrf_token": token}


@router.post("/auth/register", status_code=201, dependencies=[Depends(csrf)])
async def register(body: RegisterInput, request: Request, response: Response) -> dict[str, Any]:
    await service(request).rate_limit("register", client_ip(request), body.email)
    result = await service(request).register(body.name, body.email, body.password)
    return session_response(request, response, result)


@router.post("/auth/login", dependencies=[Depends(csrf)])
async def login(body: LoginInput, request: Request, response: Response) -> dict[str, Any]:
    await service(request).rate_limit("login", client_ip(request), body.email)
    result = await service(request).login(body.email, body.password)
    return session_response(request, response, result)


@router.post("/auth/refresh", dependencies=[Depends(csrf)])
async def refresh(request: Request, response: Response) -> dict[str, Any]:
    await service(request).rate_limit("refresh", client_ip(request))
    result = await service(request).refresh(
        request.cookies.get("forge_refresh"), request.headers["x-csrf-token"]
    )
    return session_response(request, response, result)


@router.post("/auth/logout", status_code=204, dependencies=[Depends(csrf)])
async def logout(request: Request, response: Response) -> None:
    actor = await service(request).csrf_actor(
        request.cookies.get("forge_access"), request.cookies.get("forge_refresh")
    )
    if actor:
        await service(request).logout(actor)
    clear_cookies(request, response)


@router.get("/auth/me")
async def me(request: Request, actor: Current) -> dict[str, Any]:
    result = await organizations(request).list(actor, 100, None)
    return {
        "user": actor.user(),
        "session_id": str(actor.session_id),
        "organizations": result["data"],
        "organizations_page": result["page"],
    }


@router.post("/auth/verify-email/request", status_code=202, dependencies=[Depends(csrf)])
async def request_verification(body: EmailInput, request: Request) -> dict[str, str]:
    await service(request).rate_limit("verify_request", client_ip(request), body.email)
    await service(request).request_identity(body.email, "verify")
    return {"detail": "If verification is needed for this address, a link has been sent."}


@router.post("/auth/password-reset/request", status_code=202, dependencies=[Depends(csrf)])
async def request_reset(body: EmailInput, request: Request) -> dict[str, str]:
    await service(request).rate_limit("reset_request", client_ip(request), body.email)
    await service(request).request_identity(body.email, "reset")
    return {"detail": "If an account matches this address, a reset link has been sent."}


@router.post("/auth/verify-email/confirm", dependencies=[Depends(csrf)])
async def confirm_verification(body: TokenInput, request: Request) -> dict[str, str]:
    await service(request).rate_limit("verify_confirm", client_ip(request))
    await service(request).confirm_identity(body.token, "verify")
    return {"detail": "Your email has been verified."}


@router.post("/auth/password-reset/confirm", dependencies=[Depends(csrf)])
async def confirm_reset(body: ResetInput, request: Request, response: Response) -> dict[str, str]:
    await service(request).rate_limit("reset_confirm", client_ip(request))
    await service(request).confirm_identity(body.token, "reset", body.password)
    clear_cookies(request, response)
    return {"detail": "Your password has been reset. Sign in with your new password."}


@router.get("/auth/sessions")
async def sessions(
    request: Request, actor: Current, limit: Limit = 50, cursor: Cursor = None
) -> dict[str, Any]:
    return await service(request).list_sessions(actor, limit, cursor)


@router.delete("/auth/sessions/{session_id}", status_code=204, dependencies=[Depends(csrf)])
async def revoke_session(
    session_id: UUID, request: Request, response: Response, actor: Current
) -> None:
    await service(request).revoke_session(actor, session_id)
    if actor.session_id == session_id:
        clear_cookies(request, response)


@router.get("/organizations")
async def list_organizations(
    request: Request, actor: Current, limit: Limit = 50, cursor: Cursor = None
) -> dict[str, Any]:
    return await organizations(request).list(actor, limit, cursor)


@router.post("/organizations", status_code=201, dependencies=[Depends(csrf)])
async def create_organization(
    body: OrganizationInput, request: Request, actor: Current
) -> dict[str, Any]:
    await service(request).rate_limit("organization_create", client_ip(request), str(actor.user_id))
    return await organizations(request).create(actor, body.name, body.slug)


@router.get("/organizations/{organization_id}")
async def get_organization(
    organization_id: UUID, request: Request, actor: Current
) -> dict[str, Any]:
    return await organizations(request).get(actor, organization_id)


@router.patch("/organizations/{organization_id}", dependencies=[Depends(csrf)])
async def rename_organization(
    organization_id: UUID, body: OrganizationName, request: Request, actor: Current
) -> dict[str, Any]:
    return await organizations(request).rename(actor, organization_id, body.name)


@router.delete("/organizations/{organization_id}", status_code=204, dependencies=[Depends(csrf)])
async def delete_organization(organization_id: UUID, request: Request, actor: Current) -> None:
    await organizations(request).delete(actor, organization_id)


@router.get("/organizations/{organization_id}/members")
async def list_members(
    organization_id: UUID,
    request: Request,
    actor: Current,
    limit: Limit = 50,
    cursor: Cursor = None,
) -> dict[str, Any]:
    return await organizations(request).members(actor, organization_id, limit, cursor)


@router.patch("/organizations/{organization_id}/members/{member_id}", dependencies=[Depends(csrf)])
async def change_member(
    organization_id: UUID, member_id: UUID, body: RoleInput, request: Request, actor: Current
) -> Any:
    return await organizations(request).change_member(actor, organization_id, member_id, body.role)


@router.delete(
    "/organizations/{organization_id}/members/{member_id}",
    status_code=204,
    dependencies=[Depends(csrf)],
)
async def remove_member(
    organization_id: UUID, member_id: UUID, request: Request, actor: Current
) -> None:
    await organizations(request).change_member(actor, organization_id, member_id, None)


@router.post(
    "/organizations/{organization_id}/invitations", status_code=201, dependencies=[Depends(csrf)]
)
async def invite(
    organization_id: UUID, body: InvitationInput, request: Request, actor: Current
) -> dict[str, Any]:
    await service(request).rate_limit("invite", client_ip(request), str(actor.user_id))
    return await organizations(request).invite(actor, organization_id, body.email, body.role)


@router.post("/invitations/accept", dependencies=[Depends(csrf)])
async def accept(body: TokenInput, request: Request, actor: Current) -> dict[str, Any]:
    await service(request).rate_limit("invite_accept", client_ip(request), str(actor.user_id))
    return await organizations(request).accept(actor, body.token)


@router.get("/organizations/{organization_id}/audit")
async def audit(
    organization_id: UUID,
    request: Request,
    actor: Current,
    limit: Limit = 50,
    cursor: Cursor = None,
) -> dict[str, Any]:
    return await organizations(request).audit(actor, organization_id, limit, cursor)
