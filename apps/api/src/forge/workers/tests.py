"""Parse bounded encrypted reports outside transactions, then atomically commit fenced evidence."""

import asyncio
import logging

from cryptography.fernet import InvalidToken

from forge.domain.identity import DomainError
from forge.domain.tests import payload_cipher
from forge.integrations.junit import JUnitError, parse_junit
from forge.repositories.pipeline import Lease, LostLease
from forge.repositories.tests import TestRepository

logger = logging.getLogger("forge.tests")


class TestWorker:
    def __init__(self, repository: TestRepository, secret: str) -> None:
        self.repository = repository
        self.cipher = payload_cipher(secret)

    async def run(self, lease: Lease) -> None:
        try:
            async with asyncio.timeout(50):
                async with self.repository.transaction() as connection:
                    await self.repository.tenant(connection, lease.organization_id)
                    job, report = await self.repository.report_work(connection, lease)
                    if job["attempts"] > 3:
                        raise DomainError(
                            409, "attempts_exhausted", "Report processing attempts were exhausted."
                        )
                    await self.repository.execute(
                        connection,
                        "UPDATE forge.test_reports SET status='processing' "
                        "WHERE organization_id=:org AND id=:id",
                        org=lease.organization_id,
                        id=report["id"],
                    )
                payload = self.cipher.decrypt(bytes(report["payload"]), ttl=86400)
                parsed = await asyncio.to_thread(
                    parse_junit, payload, framework=report["framework"]
                )
                del payload
                async with self.repository.transaction() as connection:
                    await self.repository.tenant(connection, lease.organization_id)
                    _, current = await self.repository.report_work(connection, lease)
                    await self.repository.persist_report(connection, current, parsed)
                    await self.repository.finish_job(connection, lease)
            logger.info("test_report.completed", extra={"job_id": str(lease.id)})
        except LostLease:
            logger.info("test_report.discarded", extra={"job_id": str(lease.id)})
        except (JUnitError, DomainError) as error:
            await self.failed(lease, error.code)
        except InvalidToken:
            await self.failed(lease, "payload_unavailable")
        except TimeoutError:
            await self.failed(lease, "processing_timeout", retry=True)
        except Exception:
            # Unknown exceptions may contain driver data or report text. Log only a fixed code.
            await self.failed(lease, "processing_failed", retry=True)

    async def failed(self, lease: Lease, code: str, *, retry: bool = False) -> None:
        try:
            await self.repository.fail_report(lease, code, retry=retry)
            logger.info("test_report.failed", extra={"job_id": str(lease.id), "error_code": code})
        except LostLease:
            logger.info("test_report.discarded", extra={"job_id": str(lease.id)})
