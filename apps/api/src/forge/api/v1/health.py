from typing import Annotated, Literal, cast

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from starlette.responses import JSONResponse

from forge import __version__
from forge.api.problems import problem
from forge.services.health import HealthService

router = APIRouter(prefix="/health", tags=["health"])


class LivenessResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str = "forge-api"
    version: str = __version__


class ReadinessChecks(BaseModel):
    database: Literal["up", "down"]
    migrations: Literal["current", "pending", "unknown"]


class ReadinessResponse(BaseModel):
    status: Literal["ready"] = "ready"
    checks: ReadinessChecks


def get_health_service(request: Request) -> HealthService:
    return cast(HealthService, request.app.state.health_service)


@router.get("/live", response_model=LivenessResponse)
async def liveness() -> LivenessResponse:
    return LivenessResponse()


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={503: {"description": "Database unavailable or migrations not current"}},
)
async def readiness(
    request: Request, service: Annotated[HealthService, Depends(get_health_service)]
) -> ReadinessResponse | JSONResponse:
    state = await service.readiness()
    checks = ReadinessChecks(
        database="up" if state.database_up else "down",
        migrations=("current" if state.migrations_current else "pending")
        if state.database_up
        else "unknown",
    )
    if not state.ready:
        return problem(
            request,
            status=503,
            code="not_ready",
            title="Service not ready",
            detail="Database connectivity or schema readiness requires attention.",
            extensions={"checks": checks.model_dump()},
        )
    return ReadinessResponse(checks=checks)
