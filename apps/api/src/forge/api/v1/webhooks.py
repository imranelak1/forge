from fastapi import APIRouter, Request
from starlette.responses import JSONResponse

from forge.domain.identity import DomainError
from forge.services.webhooks import GitHubWebhookService

router = APIRouter()


@router.post("/webhooks/github")
async def github_delivery(request: Request) -> JSONResponse:
    if (
        request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        != "application/json"
        or request.headers.get("content-encoding", "identity").lower() != "identity"
    ):
        raise DomainError(415, "unsupported_content_type", "Send an uncompressed JSON delivery.")
    for name in ("x-hub-signature-256", "x-github-delivery", "x-github-event"):
        if len(request.headers.getlist(name)) != 1:
            raise DomainError(400, "invalid_delivery", "Missing or ambiguous webhook headers.")
    service: GitHubWebhookService = request.app.state.webhook_service
    result = await service.receive(
        await request.body(),
        request.headers.get("x-hub-signature-256"),
        request.headers.get("x-github-delivery"),
        request.headers.get("x-github-event"),
    )
    return JSONResponse(
        {"receipt_id": str(result.id), "status": result.status, "reason": result.reason},
        status_code=200 if result.duplicate else 202,
    )
