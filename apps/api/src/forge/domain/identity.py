from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class Role(StrEnum):
    VIEWER = "viewer"
    MEMBER = "member"
    ADMIN = "admin"
    OWNER = "owner"


class DomainError(Exception):
    def __init__(self, status: int, code: str, detail: str) -> None:
        self.status, self.code, self.detail = status, code, detail
        super().__init__(detail)


@dataclass(frozen=True)
class Actor:
    user_id: UUID
    session_id: UUID
    name: str
    email: str
    email_verified: bool
    csrf_hash: str

    def user(self) -> dict[str, object]:
        return {
            "id": str(self.user_id),
            "name": self.name,
            "email": self.email,
            "email_verified": self.email_verified,
        }


def require_manager(role: str, target: str | None = None, new_role: str | None = None) -> None:
    if role not in {Role.ADMIN, Role.OWNER}:
        raise DomainError(403, "forbidden", "This operation requires an administrator.")
    if role != Role.OWNER and Role.OWNER in {target, new_role}:
        raise DomainError(403, "forbidden", "Only an owner can manage ownership.")


def unauthorized() -> DomainError:
    return DomainError(401, "unauthorized", "Sign in to continue.")


def not_found() -> DomainError:
    return DomainError(404, "not_found", "The requested resource is unavailable.")
