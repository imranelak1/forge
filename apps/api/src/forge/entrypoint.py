import logging
import os
import sys

from forge.config import Settings
from forge.migration import upgrade_database
from forge.observability.logging import configure_logging


def main() -> None:
    configure_logging(os.environ.get("FORGE_LOG_LEVEL", "INFO"))
    logger = logging.getLogger("forge.startup")
    try:
        upgrade_database(Settings())
    except Exception as error:
        logger.error("migration.failed", extra={"error_type": type(error).__name__})
        sys.exit(1)
    logger.info("migration.completed")
    # The web process never retains the DDL credential after startup migration.
    environment = dict(os.environ)
    environment.pop("FORGE_MIGRATION_PASSWORD", None)
    os.execve(
        sys.executable,
        [
            sys.executable,
            "-m",
            "uvicorn",
            "forge.main:create_app",
            "--factory",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
            "--no-access-log",
        ],
        environment,
    )


if __name__ == "__main__":
    main()
