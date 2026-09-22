import json
import logging
import sys
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "service": "forge-worker" if record.name.startswith("forge.worker") else "forge-api",
            "event": record.getMessage(),
        }
        for key in (
            "request_id",
            "method",
            "path",
            "status",
            "duration_ms",
            "error_type",
            "provider",
            "oauth_stage",
            "oauth_error",
            "oauth_reason",
            "organization_id",
            "job_id",
            "fence",
            "error_code",
        ):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("forge")
    logger.handlers = [handler]
    logger.setLevel(level)
    logger.propagate = False
