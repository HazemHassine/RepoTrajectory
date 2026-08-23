import asyncio
import base64
import binascii
import hashlib
import hmac
import json
import secrets
import time
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import Depends, HTTPException, Request, Response, status

from app.core.config import Settings, get_settings

ADMIN_COOKIE = "repotrajectory_admin"
PBKDF2_ITERATIONS = 600_000


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_admin_password(password: str, *, salt: bytes | None = None) -> str:
    """Return a salted PBKDF2-HMAC-SHA256 hash suitable for local admin bootstrap."""
    if not 12 <= len(password) <= 256:
        raise ValueError("admin password must contain between 12 and 256 characters")
    actual_salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), actual_salt, PBKDF2_ITERATIONS
    )
    return f"pbkdf2_sha256:{PBKDF2_ITERATIONS}:{_encode(actual_salt)}:{_encode(digest)}"


def verify_admin_password(password: str, encoded: str) -> bool:
    if len(password) > 256:
        return False
    try:
        algorithm, iterations_text, salt_text, expected_text = encoded.split(":", 3)
        iterations = int(iterations_text)
        if algorithm != "pbkdf2_sha256" or not 100_000 <= iterations <= 2_000_000:
            return False
        salt = _decode(salt_text)
        expected = _decode(expected_text)
    except (ValueError, TypeError):
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)


@dataclass(frozen=True)
class AdminSession:
    username: str
    csrf_token: str
    issued_at: datetime
    expires_at: datetime


def _configured(settings: Settings) -> bool:
    return bool(settings.admin_password_hash and settings.admin_session_secret)


def require_admin_configuration(settings: Settings) -> None:
    if not _configured(settings) or len(settings.admin_session_secret or "") < 32:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Admin access is disabled until local credentials are configured.",
        )


def create_admin_session(settings: Settings) -> tuple[str, AdminSession]:
    require_admin_configuration(settings)
    now = int(time.time())
    expires = now + settings.admin_session_hours * 3600
    payload = {
        "sub": settings.admin_username,
        "iat": now,
        "exp": expires,
        "csrf": secrets.token_urlsafe(24),
        "nonce": secrets.token_urlsafe(12),
    }
    encoded_payload = _encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    signature = hmac.new(
        (settings.admin_session_secret or "").encode("utf-8"),
        encoded_payload.encode("ascii"),
        hashlib.sha256,
    ).digest()
    session = AdminSession(
        username=settings.admin_username,
        csrf_token=str(payload["csrf"]),
        issued_at=datetime.fromtimestamp(now, UTC),
        expires_at=datetime.fromtimestamp(expires, UTC),
    )
    return f"{encoded_payload}.{_encode(signature)}", session


def decode_admin_session(token: str, settings: Settings, *, now: int | None = None) -> AdminSession:
    require_admin_configuration(settings)
    try:
        encoded_payload, encoded_signature = token.split(".", 1)
        expected_signature = hmac.new(
            (settings.admin_session_secret or "").encode("utf-8"),
            encoded_payload.encode("ascii"),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(expected_signature, _decode(encoded_signature)):
            raise ValueError("invalid signature")
        payload = json.loads(_decode(encoded_payload))
        current = int(time.time()) if now is None else now
        issued_at = int(payload["iat"])
        expires_at = int(payload["exp"])
        if payload["sub"] != settings.admin_username:
            raise ValueError("invalid subject")
        if issued_at > current + 60 or expires_at <= current or expires_at <= issued_at:
            raise ValueError("expired session")
        csrf_token = str(payload["csrf"])
        if len(csrf_token) < 24:
            raise ValueError("invalid csrf token")
    except (
        ValueError,
        TypeError,
        KeyError,
        json.JSONDecodeError,
        UnicodeDecodeError,
        binascii.Error,
    ) as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Admin session is invalid or expired"
        ) from exc
    return AdminSession(
        username=settings.admin_username,
        csrf_token=csrf_token,
        issued_at=datetime.fromtimestamp(issued_at, UTC),
        expires_at=datetime.fromtimestamp(expires_at, UTC),
    )


def set_admin_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        key=ADMIN_COOKIE,
        value=token,
        max_age=settings.admin_session_hours * 3600,
        httponly=True,
        secure=settings.admin_secure_cookies,
        samesite="strict",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"


def clear_admin_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        ADMIN_COOKIE,
        path="/",
        secure=settings.admin_secure_cookies,
        httponly=True,
        samesite="strict",
    )
    response.headers["Cache-Control"] = "no-store"


def validate_admin_origin(request: Request, settings: Settings) -> None:
    if request.headers.get("sec-fetch-site", "").lower() == "cross-site":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cross-site admin requests are blocked")
    source = request.headers.get("origin")
    if not source:
        referer = request.headers.get("referer")
        if referer:
            parsed = urlsplit(referer)
            source = f"{parsed.scheme}://{parsed.netloc}"
    normalized = source.rstrip("/").casefold() if source else None
    if normalized not in settings.admin_allowed_origin_list:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin request origin is not allowed")


async def require_admin_session(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> AdminSession:
    token = request.cookies.get(ADMIN_COOKIE)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Admin authentication required")
    return decode_admin_session(token, settings)


async def require_admin_mutation(
    request: Request,
    session: Annotated[AdminSession, Depends(require_admin_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AdminSession:
    validate_admin_origin(request, settings)
    supplied = request.headers.get("x-csrf-token", "")
    if not supplied or not hmac.compare_digest(supplied, session.csrf_token):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "CSRF validation failed")
    return session


class LoginRateLimiter:
    """Small in-process limiter; the deployment runs a single private API worker by default."""

    def __init__(self, attempts: int = 5, window_seconds: int = 15 * 60) -> None:
        self.attempts = attempts
        self.window_seconds = window_seconds
        self._failures: dict[str, deque[float]] = {}
        self._lock = asyncio.Lock()

    async def check(self, key: str) -> None:
        async with self._lock:
            failures = self._current(key)
            if len(failures) >= self.attempts:
                retry_after = max(1, int(self.window_seconds - (time.monotonic() - failures[0])))
                raise HTTPException(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    "Too many login attempts. Try again later.",
                    headers={"Retry-After": str(retry_after)},
                )

    async def failed(self, key: str) -> None:
        async with self._lock:
            self._current(key).append(time.monotonic())

    async def succeeded(self, key: str) -> None:
        async with self._lock:
            self._failures.pop(key, None)

    def _current(self, key: str) -> deque[float]:
        failures = self._failures.setdefault(key, deque())
        cutoff = time.monotonic() - self.window_seconds
        while failures and failures[0] < cutoff:
            failures.popleft()
        return failures


login_rate_limiter = LoginRateLimiter()
