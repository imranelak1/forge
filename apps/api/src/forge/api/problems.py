from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse


def problem(
    request: Request,
    *,
    status: int,
    code: str,
    title: str,
    detail: str,
    extensions: dict[str, Any] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        media_type="application/problem+json",
        content={
            "type": f"urn:forge:problem:{code}",
            "title": title,
            "status": status,
            "code": code,
            "detail": detail,
            "instance": request.url.path,
            "request_id": getattr(request.state, "request_id", "unknown"),
            **(extensions or {}),
        },
    )
