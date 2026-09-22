"""Authenticate GitHub deliveries, resolve tenant routing, and commit before acknowledging."""

import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from uuid import UUID

from forge.config import Settings
from forge.domain.identity import DomainError
from forge.repositories.identity import IdentityRepository
from forge.repositories.webhooks import WebhookRepository

SUPPORTED_ACTIONS = {
    "pull_request_review": {"submitted", "edited", "dismissed"},
    "issues": {"opened", "edited", "closed", "reopened", "transferred"},
    "pull_request": {
        "opened",
        "edited",
        "closed",
        "reopened",
        "synchronize",
        "ready_for_review",
        "converted_to_draft",
        "labeled",
        "unlabeled",
        "assigned",
        "unassigned",
        "review_requested",
        "review_request_removed",
        "locked",
        "unlocked",
        "auto_merge_enabled",
        "auto_merge_disabled",
        "enqueued",
        "dequeued",
    },
    "installation": {"created", "deleted", "suspend", "unsuspend", "new_permissions_accepted"},
    "installation_repositories": {"added", "removed"},
}


def source_id(value: object) -> int | None:
    return value if type(value) is int and 0 < value < 2**63 else None


@dataclass(frozen=True)
class WebhookReceipt:
    id: UUID
    status: str
    reason: str | None
    duplicate: bool = False


class GitHubWebhookService:
    def __init__(self, settings: Settings, repository: IdentityRepository) -> None:
        self.settings = settings
        self.repository = WebhookRepository(repository.engine)
        self.pipeline = self.repository

    def verify(self, body: bytes, signature: str | None) -> None:
        secret = self.settings.github_app_webhook_secret
        if secret is None:
            raise DomainError(503, "integration_unavailable", "GitHub App is not configured.")
        expected = (
            "sha256="
            + hmac.new(secret.get_secret_value().encode(), body, hashlib.sha256).hexdigest()
        )
        if (
            not signature
            or not re.fullmatch(r"sha256=[0-9a-f]{64}", signature)
            or not hmac.compare_digest(expected, signature)
        ):
            raise DomainError(401, "invalid_signature", "Webhook signature verification failed.")

    async def receive(
        self, body: bytes, signature: str | None, delivery: str | None, event: str | None
    ) -> WebhookReceipt:
        self.verify(body, signature)
        try:
            if not delivery or len(delivery) != 36 or not event:
                raise ValueError
            identifier = UUID(delivery)
            if not re.fullmatch(r"[a-z_]{1,80}", event):
                raise ValueError
            payload = json.loads(body)
            if not isinstance(payload, dict):
                raise ValueError
        except (ValueError, UnicodeError, RecursionError) as exc:
            raise DomainError(400, "invalid_delivery", "Invalid GitHub webhook delivery.") from exc
        digest = hashlib.sha256(body).hexdigest()
        repo = self.repository
        async with repo.transaction() as connection:
            previous = await repo.receipt(connection, identifier)
            if previous:
                if previous["digest"] != digest or previous["event"] != event:
                    raise DomainError(
                        409,
                        "delivery_conflict",
                        "Delivery ID was already used for different content.",
                    )
                return WebhookReceipt(identifier, previous["status"], previous["reason"], True)
            installation = payload.get("installation")
            installation_id = (
                source_id(installation.get("id")) if isinstance(installation, dict) else None
            )
            binding = await repo.binding(connection, installation_id) if installation_id else None
            reason: str | None = None
            integration = None
            organization_id, integration_id = None, None
            if binding:
                organization_id = binding["organization_id"]
                integration_id = binding["integration_id"]
                integration = await repo.mapped_integration(
                    connection, organization_id, integration_id
                )
            if event == "ping":
                reason = "ping"
            elif event not in {"push", *SUPPORTED_ACTIONS}:
                reason = "unsupported_event"
            elif event in SUPPORTED_ACTIONS and (
                not isinstance(payload.get("action"), str)
                or payload["action"] not in SUPPORTED_ACTIONS[event]
            ):
                reason = "unsupported_action"
            elif not binding:
                reason = "unbound_installation"
            elif not integration:
                reason = reason or "integration_unavailable"
            elif integration["status"] == "disconnected":
                reason = "integration_disconnected"
            elif event in {"push", "pull_request", "pull_request_review", "issues"}:
                assert organization_id is not None and integration_id is not None
                if integration["status"] != "active":
                    reason = "integration_inactive"
                source_repo = payload.get("repository")
                repository_id = (
                    source_id(source_repo.get("id")) if isinstance(source_repo, dict) else None
                )
                authorized = (
                    await repo.selected_repository(
                        connection, organization_id, integration_id, repository_id
                    )
                    if repository_id
                    else None
                )
                if not authorized:
                    reason = reason or "repository_not_selected"
            state = "ignored" if reason else "queued"
            await repo.create_receipt(
                connection,
                identifier,
                digest,
                event,
                state,
                reason,
                organization_id,
                integration_id,
            )
            if reason:
                return WebhookReceipt(identifier, state, reason)
            assert (
                integration is not None
                and organization_id is not None
                and integration_id is not None
            )
            # Source revocations take effect before an acknowledgement, even while
            # workers are fetching an older page. Their commit guard sees the change.
            action = payload.get("action")
            if event == "installation" and action in {"deleted", "suspend"}:
                status = "disconnected" if action == "deleted" else "suspended"
                await repo.revoke_installation(connection, organization_id, integration_id, status)
                state, reason = "processed", "access_revoked"
            if event == "installation_repositories":
                removed = payload.get("repositories_removed", [])
                removed_ids: list[int] = []
                if isinstance(removed, list):
                    removed_ids = [
                        removed_id
                        for item in removed
                        if isinstance(item, dict)
                        if (removed_id := source_id(item.get("id"))) is not None
                    ]
                await repo.revoke_repositories(
                    connection, organization_id, integration_id, removed_ids
                )
            await repo.accept_inbox(
                connection,
                organization_id,
                integration_id,
                identifier,
                payload,
                event,
                state,
                reason,
            )
            return WebhookReceipt(identifier, state, reason)
