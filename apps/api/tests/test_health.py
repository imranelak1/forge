from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from forge.api.v1.health import get_health_service
from forge.config import Settings
from forge.domain.health import DatabaseState
from forge.main import create_app
from forge.services.health import HealthService


class StubHealthRepository:
    def __init__(self, reachable: bool, revisions: frozenset[str]) -> None:
        self.state = DatabaseState(reachable, revisions)

    async def snapshot(self) -> DatabaseState:
        return self.state


@pytest.mark.parametrize(
    ("reachable", "revisions", "expected_status"),
    [(True, {"head"}, 200), (True, set(), 503), (True, {"old"}, 503), (False, set(), 503)],
)
def test_readiness_requires_connection_and_exact_schema(
    settings: Settings, reachable: bool, revisions: set[str], expected_status: int
) -> None:
    app = create_app(settings)
    service = HealthService(
        StubHealthRepository(reachable, frozenset(revisions)), frozenset({"head"})
    )
    app.dependency_overrides[get_health_service] = lambda: service
    with TestClient(app) as client:
        response = client.get("/api/v1/health/ready")
        assert response.status_code == expected_status
        assert response.json()["checks"]["database"] == ("up" if reachable else "down")
        if expected_status == 503:
            assert response.headers["content-type"] == "application/problem+json"
            assert response.json()["code"] == "not_ready"


def test_liveness_does_not_require_a_database_and_errors_have_request_ids(
    settings: Settings,
) -> None:
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/v1/health/live", headers={"X-Request-ID": "not-a-valid-id"})
        assert response.status_code == 200
        assert response.json()["service"] == "forge-api"
        UUID(response.headers["x-request-id"])
        response = client.get("/api/v1/missing")
        assert response.status_code == 404
        assert response.json()["request_id"] == response.headers["x-request-id"]
        assert response.headers["cache-control"] == "no-store"


def test_unexpected_errors_are_redacted(settings: Settings) -> None:
    app = create_app(settings)

    @app.get("/explode")
    async def explode() -> None:
        raise RuntimeError("private-provider-secret")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/explode")
        assert response.status_code == 500
        assert "private-provider-secret" not in response.text
        assert response.json()["code"] == "internal_error"


def test_production_does_not_expose_interactive_api_docs(settings: Settings) -> None:
    settings.environment = "production"
    with TestClient(create_app(settings)) as client:
        assert client.get("/docs").status_code == 404


def test_oversized_body_is_rejected_with_safe_common_response_headers(settings: Settings) -> None:
    with TestClient(create_app(settings)) as client:
        response = client.post("/api/v1/auth/register", content=b"x" * 16385)
        assert response.status_code == 413
        assert response.headers["content-type"] == "application/problem+json"
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.json()["request_id"] == response.headers["x-request-id"]
