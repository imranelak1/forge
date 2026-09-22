import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from time import perf_counter
from uuid import UUID, uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.responses import Response

from forge import __version__
from forge.api.problems import problem
from forge.api.v1.health import router as health_router
from forge.api.v1.identity import router as identity_router
from forge.config import Settings
from forge.domain.identity import DomainError
from forge.migration import migration_heads
from forge.observability.logging import configure_logging
from forge.repositories.database import create_database_engine
from forge.repositories.health import PostgresHealthRepository
from forge.repositories.identity import IdentityRepository
from forge.services.health import HealthService
from forge.services.identity import IdentityService
from forge.services.organizations import OrganizationService

logger = logging.getLogger("forge.http")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    configure_logging(settings.log_level)
    engine = create_database_engine(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        await engine.dispose()

    app = FastAPI(
        title="Forge API",
        description="Engineering intelligence. Authentication and SaaS foundation.",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url=None,
        openapi_url="/api/v1/openapi.json" if settings.environment != "production" else None,
    )
    app.state.health_service = HealthService(PostgresHealthRepository(engine), migration_heads())
    app.state.settings = settings
    app.state.identity_service = IdentityService(IdentityRepository(engine), settings)
    app.state.organization_service = OrganizationService(app.state.identity_service)

    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        try:
            request_id = str(UUID(request.headers.get("x-request-id", "")))
        except ValueError:
            request_id = str(uuid4())
        request.state.request_id = request_id
        started = perf_counter()
        response: Response
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            # Read a bounded stream even if Content-Length is absent or dishonest.
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 16384:
                    response = problem(
                        request,
                        status=413,
                        code="body_too_large",
                        title="Request too large",
                        detail="Request bodies must be smaller than 16 KiB.",
                    )
                    response.headers["X-Request-ID"] = request_id
                    response.headers["Cache-Control"] = "no-store"
                    response.headers["X-Content-Type-Options"] = "nosniff"
                    return response
            request._body = bytes(body)
        try:
            response = await call_next(request)
        except Exception as error:
            logger.error(
                "request.failed",
                extra={"request_id": request_id, "error_type": type(error).__name__},
            )
            response = problem(
                request,
                status=500,
                code="internal_error",
                title="Unexpected server error",
                detail="The request could not be completed. Use the request ID when reporting it.",
            )
        response.headers["X-Request-ID"] = request_id
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        logger.info(
            "request.completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((perf_counter() - started) * 1000, 2),
            },
        )
        return response

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException) -> Response:
        return problem(
            request,
            status=error.status_code,
            code="not_found" if error.status_code == 404 else "http_error",
            title="Request could not be completed",
            detail="The requested resource or operation is unavailable.",
        )

    @app.exception_handler(DomainError)
    async def domain_error(request: Request, error: DomainError) -> Response:
        response = problem(
            request,
            status=error.status,
            code=error.code,
            title="Request could not be completed",
            detail=error.detail,
        )
        if error.status == 429:
            response.headers["Retry-After"] = "900"
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError) -> Response:
        return problem(
            request,
            status=422,
            code="validation_error",
            title="Invalid request",
            detail="One or more fields failed validation.",
            extensions={
                "errors": [
                    {"field": list(item["loc"]), "code": item["type"]}
                    for item in error.errors()[:20]
                ]
            },
        )

    app.include_router(health_router, prefix="/api/v1")
    app.include_router(identity_router, prefix="/api/v1")
    return app
