"""Fixed-endpoint GitHub App transport; short-lived credentials stay server-side."""

import base64
import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

from forge.config import Settings

API_VERSION = "2026-03-10"
API_ORIGIN = "https://api.github.com"
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_PAGES = 100


class GitHubFailure(Exception):
    def __init__(
        self, code: str, *, retryable: bool = False, retry_after: int | None = None
    ) -> None:
        self.code, self.retryable, self.retry_after = code, retryable, retry_after
        super().__init__(code)


def segment(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", value) or value in {".", ".."}:
        raise GitHubFailure("invalid_resource")
    return value


def positive_id(value: object) -> int:
    if type(value) is not int or not 0 < value <= 9223372036854775807:
        raise GitHubFailure("invalid_response")
    return value


def token_value(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 8192
        or not value.isascii()
        or any(ord(character) < 33 or ord(character) == 127 for character in value)
    ):
        raise GitHubFailure("invalid_response")
    return value


def retry_delay(headers: httpx.Headers) -> int | None:
    value = headers.get("retry-after")
    if value:
        try:
            seconds = int(value)
        except ValueError:
            try:
                seconds = int((parsedate_to_datetime(value) - datetime.now(UTC)).total_seconds())
            except (ValueError, TypeError, OverflowError):
                seconds = 60
        return min(86400, max(1, seconds))
    reset = headers.get("x-ratelimit-reset")
    if reset:
        try:
            return min(86400, max(1, int(reset) - int(datetime.now(UTC).timestamp())))
        except ValueError:
            return 60
    return None


class GitHubApp:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(8.0, connect=3.0),
            follow_redirects=False,
            trust_env=False,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=5),
        )
        self.private_key: RSAPrivateKey | None = None
        if settings.github_app_private_key_base64:
            key = serialization.load_pem_private_key(
                base64.b64decode(settings.github_app_private_key_base64.get_secret_value()), None
            )
            assert isinstance(key, RSAPrivateKey)
            self.private_key = key

    @property
    def configured(self) -> bool:
        return self.settings.github_app_id is not None

    @property
    def install_url(self) -> str | None:
        if not self.configured:
            return None
        return f"https://github.com/apps/{self.settings.github_app_slug}/installations/new"

    def require_configured(self) -> None:
        if not self.configured:
            raise GitHubFailure("not_configured")

    @property
    def callback_url(self) -> str:
        return f"{self.settings.public_origin}/api/v1/integrations/github/callback"

    def app_jwt(self) -> str:
        self.require_configured()
        assert self.private_key is not None
        issued = datetime.now(UTC)
        return jwt.encode(
            {
                "iat": issued - timedelta(seconds=60),
                "exp": issued + timedelta(minutes=9),
                "iss": self.settings.github_app_client_id,
            },
            self.private_key,
            algorithm="RS256",
        )

    def authorization_url(self, state: str, verifier: str) -> str:
        self.require_configured()
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .decode()
            .rstrip("=")
        )
        return "https://github.com/login/oauth/authorize?" + urlencode(
            {
                "client_id": self.settings.github_app_client_id,
                "redirect_uri": self.callback_url,
                "state": state,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
        )

    async def request(
        self,
        method: str,
        path: str,
        token: str | None = None,
        *,
        params: dict[str, str | int] | None = None,
        payload: dict[str, Any] | None = None,
        form: dict[str, str] | None = None,
    ) -> Any:
        # Every call uses a path authored here, never a URL from a provider response.
        if (
            not path.startswith("/")
            or path.startswith("//")
            or "\\" in path
            or ".." in path.split("/")
        ):
            raise GitHubFailure("invalid_resource")
        url = (
            "https://github.com/login/oauth/access_token" if form is not None else API_ORIGIN + path
        )
        headers = {
            "Accept": "application/json" if form is not None else "application/vnd.github+json",
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": "Forge-GitHub-App",
        }
        if token is not None:
            headers["Authorization"] = "Bearer " + token_value(token)
        try:
            async with self.client.stream(
                method, url, params=params, json=payload, data=form, headers=headers
            ) as response:
                status = response.status_code
                if status == 429 or (
                    status == 403
                    and (
                        response.headers.get("x-ratelimit-remaining") == "0"
                        or "retry-after" in response.headers
                    )
                ):
                    raise GitHubFailure(
                        "rate_limited",
                        retryable=True,
                        retry_after=retry_delay(response.headers) or 60,
                    )
                if status >= 500:
                    raise GitHubFailure(
                        "provider_unavailable",
                        retryable=True,
                        retry_after=retry_delay(response.headers),
                    )
                if status == 401:
                    raise GitHubFailure("credentials_rejected")
                if status in {403, 404}:
                    raise GitHubFailure("access_denied")
                empty_repository = (
                    status == 409
                    and method == "GET"
                    and bool(re.fullmatch(r"/repos/[^/]+/[^/]+/commits", path))
                )
                if not 200 <= status < 300 and not empty_repository:
                    raise GitHubFailure("invalid_response")
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_RESPONSE_BYTES:
                        raise GitHubFailure("response_too_large")
                decoded = json.loads(body)
                if empty_repository:
                    if (
                        isinstance(decoded, dict)
                        and decoded.get("message") == "Git Repository is empty."
                    ):
                        return []
                    raise GitHubFailure("repository_conflict")
                return decoded
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise GitHubFailure("provider_unavailable", retryable=True) from exc
        except (httpx.HTTPError, ValueError, UnicodeError) as exc:
            raise GitHubFailure("invalid_response") from exc

    async def exchange_user_code(self, code: str, verifier: str) -> str:
        self.require_configured()
        assert self.settings.github_app_client_id and self.settings.github_app_client_secret
        data = await self.request(
            "POST",
            "/login/oauth/access_token",
            form={
                "client_id": self.settings.github_app_client_id,
                "client_secret": self.settings.github_app_client_secret.get_secret_value(),
                "code": code,
                "code_verifier": verifier,
                "redirect_uri": self.callback_url,
            },
        )
        if not isinstance(data, dict) or data.get("error"):
            raise GitHubFailure("authorization_failed")
        return token_value(data.get("access_token"))

    def validate_installation(self, data: object) -> dict[str, Any]:
        if (
            not isinstance(data, dict)
            or type(data.get("app_id")) is not int
            or data.get("app_id") != self.settings.github_app_id
        ):
            raise GitHubFailure("installation_mismatch")
        positive_id(data.get("id"))
        if data.get("suspended_at") is not None:
            raise GitHubFailure("installation_suspended")
        permissions = data.get("permissions")
        if not isinstance(permissions, dict) or any(
            permissions.get(name) not in {"read", "write"} for name in ("contents", "pull_requests")
        ):
            raise GitHubFailure("permissions_required")
        account = data.get("account")
        if (
            not isinstance(account, dict)
            or not isinstance(account.get("login"), str)
            or not 0 < len(account["login"]) <= 100
            or account.get("type") not in {"User", "Organization"}
        ):
            raise GitHubFailure("invalid_response")
        if data.get("repository_selection") not in {"all", "selected"}:
            raise GitHubFailure("invalid_response")
        return data

    async def require_account_admin(self, token: str, installation: dict[str, Any]) -> None:
        account = self.validate_installation(installation)["account"]
        account_id = positive_id(account.get("id"))
        if account["type"] == "User":
            user = await self.request("GET", "/user", token)
            if (
                not isinstance(user, dict)
                or type(user.get("id")) is not int
                or user["id"] != account_id
            ):
                raise GitHubFailure("installation_admin_required")
            return
        if installation["permissions"].get("members") not in {"read", "write"}:
            raise GitHubFailure("permissions_required")
        try:
            membership = await self.request(
                "GET", f"/user/memberships/orgs/{segment(account['login'])}", token
            )
        except GitHubFailure as exc:
            if exc.code == "access_denied":
                raise GitHubFailure("installation_admin_required") from exc
            raise
        if (
            not isinstance(membership, dict)
            or membership.get("state") != "active"
            or membership.get("role") != "admin"
        ):
            raise GitHubFailure("installation_admin_required")
        organization = membership.get("organization")
        if (
            not isinstance(organization, dict)
            or type(organization.get("id")) is not int
            or organization["id"] != account_id
        ):
            raise GitHubFailure("installation_admin_required")

    async def user_installations(self, token: str) -> list[dict[str, Any]]:
        self.require_configured()
        result: list[dict[str, Any]] = []
        for page in range(1, MAX_PAGES + 1):
            data = await self.request(
                "GET", "/user/installations", token, params={"per_page": 100, "page": page}
            )
            batch = self.list_field(data, "installations")
            for item in batch:
                try:
                    result.append(self.validate_installation(item))
                except GitHubFailure as exc:
                    if exc.code not in {
                        "installation_suspended",
                        "permissions_required",
                        "installation_mismatch",
                    }:
                        raise
            if len(batch) < 100:
                return result
        raise GitHubFailure("capacity_exceeded")

    async def installation(self, identifier: int) -> dict[str, Any]:
        positive_id(identifier)
        data = self.validate_installation(
            await self.request("GET", f"/app/installations/{identifier}", self.app_jwt())
        )
        if data["id"] != identifier:
            raise GitHubFailure("installation_mismatch")
        return data

    async def installation_token(self, identifier: int) -> str:
        token, _ = await self.enrichment_credentials(identifier, include_issues=False)
        return token

    async def enrichment_credentials(
        self, identifier: int, *, include_issues: bool = True
    ) -> tuple[str, bool]:
        token, granted = await self.capability_credentials(
            identifier, ("issues",) if include_issues else ()
        )
        return token, "issues" in granted

    async def capability_credentials(
        self, identifier: int, optional: tuple[str, ...]
    ) -> tuple[str, frozenset[str]]:
        installation = await self.installation(identifier)
        permissions = {"contents": "read", "pull_requests": "read"}
        for name in optional:
            if name not in {"issues", "actions", "deployments"}:
                raise ValueError("invalid_capability")
            if installation["permissions"].get(name) in {"read", "write"}:
                permissions[name] = "read"
        data = await self.request(
            "POST",
            f"/app/installations/{identifier}/access_tokens",
            self.app_jwt(),
            payload={"permissions": permissions},
        )
        if (
            not isinstance(data, dict)
            or not isinstance(data.get("permissions"), dict)
            or any(
                data["permissions"].get(name) not in {"read", "write"}
                for name in ("contents", "pull_requests")
            )
        ):
            raise GitHubFailure("permissions_required")
        return token_value(data.get("token")), frozenset(
            name
            for name in optional
            if name in permissions and data["permissions"].get(name) in {"read", "write"}
        )

    async def cicd_credentials(self, identifier: int) -> tuple[str, frozenset[str]]:
        return await self.capability_credentials(identifier, ("actions", "deployments"))

    @staticmethod
    def list_field(data: object, field: str | None = None) -> list[dict[str, Any]]:
        result = data.get(field) if field is not None and isinstance(data, dict) else data
        if (
            not isinstance(result, list)
            or len(result) > 100
            or not all(isinstance(item, dict) for item in result)
        ):
            raise GitHubFailure("invalid_response")
        return result

    @staticmethod
    def page(page: int) -> int:
        if type(page) is not int or not 1 <= page <= MAX_PAGES:
            raise GitHubFailure("capacity_exceeded")
        return page

    async def repositories(self, token: str, page: int) -> list[dict[str, Any]]:
        return self.list_field(
            await self.request(
                "GET",
                "/installation/repositories",
                token,
                params={"per_page": 100, "page": self.page(page)},
            ),
            "repositories",
        )

    async def pull_requests(
        self, token: str, owner: str, name: str, page: int
    ) -> list[dict[str, Any]]:
        return self.list_field(
            await self.request(
                "GET",
                f"/repos/{segment(owner)}/{segment(name)}/pulls",
                token,
                params={
                    "per_page": 100,
                    "page": self.page(page),
                    "state": "all",
                    "sort": "updated",
                    "direction": "desc",
                },
            )
        )

    async def commits(
        self, token: str, owner: str, name: str, page: int, since: str, until: str
    ) -> list[dict[str, Any]]:
        return self.list_field(
            await self.request(
                "GET",
                f"/repos/{segment(owner)}/{segment(name)}/commits",
                token,
                params={"per_page": 100, "page": self.page(page), "since": since, "until": until},
            )
        )

    async def pull_request(self, token: str, owner: str, name: str, number: int) -> dict[str, Any]:
        positive_id(number)
        data = await self.request(
            "GET", f"/repos/{segment(owner)}/{segment(name)}/pulls/{number}", token
        )
        if not isinstance(data, dict):
            raise GitHubFailure("invalid_response")
        return data

    async def reviews(
        self, token: str, owner: str, name: str, number: int, page: int
    ) -> list[dict[str, Any]]:
        positive_id(number)
        return self.list_field(
            await self.request(
                "GET",
                f"/repos/{segment(owner)}/{segment(name)}/pulls/{number}/reviews",
                token,
                params={"per_page": 100, "page": self.page(page)},
            )
        )

    async def timeline(
        self, token: str, owner: str, name: str, number: int, page: int
    ) -> list[dict[str, Any]]:
        positive_id(number)
        return self.list_field(
            await self.request(
                "GET",
                f"/repos/{segment(owner)}/{segment(name)}/issues/{number}/timeline",
                token,
                params={"per_page": 100, "page": self.page(page)},
            )
        )

    async def pull_request_commits(
        self, token: str, owner: str, name: str, number: int, page: int
    ) -> list[dict[str, Any]]:
        positive_id(number)
        if not 1 <= self.page(page) <= 3:
            raise GitHubFailure("capacity_exceeded")
        return self.list_field(
            await self.request(
                "GET",
                f"/repos/{segment(owner)}/{segment(name)}/pulls/{number}/commits",
                token,
                params={"per_page": 100, "page": page},
            )
        )

    async def commit_details(
        self, token: str, owner: str, name: str, identifier: str, page: int
    ) -> dict[str, Any]:
        if not re.fullmatch(r"[a-f0-9]{40}", identifier) or not 1 <= self.page(page) <= 30:
            raise GitHubFailure("invalid_resource")
        data = await self.request(
            "GET",
            f"/repos/{segment(owner)}/{segment(name)}/commits/{identifier}",
            token,
            params={"per_page": 100, "page": page},
        )
        if not isinstance(data, dict) or not isinstance(data.get("files"), list):
            raise GitHubFailure("invalid_response")
        # GitHub JSON unavoidably includes patch fragments. Drop them at the adapter
        # boundary; no patch, raw_url, blob content, or provider body enters storage/logs.
        allowed = {"filename", "previous_filename", "status", "additions", "deletions", "changes"}
        files = self.list_field(data, "files")
        return {
            **{key: data.get(key) for key in ("sha", "commit", "author", "stats")},
            "files": [
                {key: value for key, value in row.items() if key in allowed} for row in files
            ],
        }

    async def issues(
        self, token: str, owner: str, name: str, page: int, since: str
    ) -> list[dict[str, Any]]:
        return self.list_field(
            await self.request(
                "GET",
                f"/repos/{segment(owner)}/{segment(name)}/issues",
                token,
                params={
                    "per_page": 100,
                    "page": self.page(page),
                    "state": "all",
                    "sort": "updated",
                    "direction": "desc",
                    "since": since,
                },
            )
        )

    async def issue(self, token: str, owner: str, name: str, number: int) -> dict[str, Any]:
        positive_id(number)
        data = await self.request(
            "GET",
            f"/repos/{segment(owner)}/{segment(name)}/issues/{number}",
            token,
        )
        if not isinstance(data, dict) or "pull_request" in data:
            raise GitHubFailure("invalid_response")
        return data

    async def workflow_runs(
        self, token: str, owner: str, name: str, page: int
    ) -> tuple[list[dict[str, Any]], int]:
        data = await self.request(
            "GET",
            f"/repos/{segment(owner)}/{segment(name)}/actions/runs",
            token,
            params={"per_page": 100, "page": self.page(page)},
        )
        values = self.list_field(data, "workflow_runs")
        total = data.get("total_count") if isinstance(data, dict) else None
        if type(total) is not int or total < 0:
            raise GitHubFailure("invalid_response")
        return values, total

    async def workflow_run(
        self, token: str, owner: str, name: str, identifier: int, attempt: int | None = None
    ) -> dict[str, Any]:
        positive_id(identifier)
        suffix = f"/attempts/{positive_id(attempt)}" if attempt is not None else ""
        data = await self.request(
            "GET",
            f"/repos/{segment(owner)}/{segment(name)}/actions/runs/{identifier}{suffix}",
            token,
        )
        if not isinstance(data, dict):
            raise GitHubFailure("invalid_response")
        return data

    async def workflow_jobs(
        self, token: str, owner: str, name: str, identifier: int, attempt: int, page: int
    ) -> tuple[list[dict[str, Any]], int]:
        positive_id(identifier)
        positive_id(attempt)
        data = await self.request(
            "GET",
            f"/repos/{segment(owner)}/{segment(name)}/actions/runs/{identifier}"
            f"/attempts/{attempt}/jobs",
            token,
            params={"per_page": 100, "page": self.page(page)},
        )
        values = self.list_field(data, "jobs")
        total = data.get("total_count") if isinstance(data, dict) else None
        if type(total) is not int or total < 0:
            raise GitHubFailure("invalid_response")
        return values, total

    async def deployments(
        self, token: str, owner: str, name: str, page: int
    ) -> list[dict[str, Any]]:
        return self.list_field(
            await self.request(
                "GET",
                f"/repos/{segment(owner)}/{segment(name)}/deployments",
                token,
                params={"per_page": 100, "page": self.page(page)},
            )
        )

    async def deployment(
        self, token: str, owner: str, name: str, identifier: int
    ) -> dict[str, Any]:
        positive_id(identifier)
        data = await self.request(
            "GET", f"/repos/{segment(owner)}/{segment(name)}/deployments/{identifier}", token
        )
        if not isinstance(data, dict):
            raise GitHubFailure("invalid_response")
        return data

    async def deployment_statuses(
        self, token: str, owner: str, name: str, identifier: int, page: int
    ) -> list[dict[str, Any]]:
        positive_id(identifier)
        return self.list_field(
            await self.request(
                "GET",
                f"/repos/{segment(owner)}/{segment(name)}/deployments/{identifier}/statuses",
                token,
                params={"per_page": 100, "page": self.page(page)},
            )
        )
