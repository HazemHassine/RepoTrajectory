import pytest
from fastapi import HTTPException

from app.core.admin_auth import (
    create_admin_session,
    decode_admin_session,
    hash_admin_password,
    verify_admin_password,
)
from app.core.config import Settings


def admin_settings() -> Settings:
    return Settings(
        _env_file=None,
        admin_username="admin",
        admin_password_hash=hash_admin_password(
            "correct horse battery staple", salt=b"0123456789abcdef"
        ),
        admin_session_secret="session-signing-secret-with-at-least-32-characters",
    )


def test_password_hash_is_salted_and_one_way() -> None:
    encoded = hash_admin_password("correct horse battery staple", salt=b"0123456789abcdef")

    assert "correct horse battery staple" not in encoded
    assert verify_admin_password("correct horse battery staple", encoded)
    assert not verify_admin_password("wrong password", encoded)


def test_signed_admin_session_rejects_tampering_and_expiry() -> None:
    settings = admin_settings()
    token, created = create_admin_session(settings)

    decoded = decode_admin_session(token, settings)
    assert decoded.username == "admin"
    assert decoded.csrf_token == created.csrf_token

    with pytest.raises(HTTPException) as tampered:
        decode_admin_session(token[:-1] + ("a" if token[-1] != "a" else "b"), settings)
    assert tampered.value.status_code == 401

    with pytest.raises(HTTPException) as expired:
        decode_admin_session(token, settings, now=int(created.expires_at.timestamp()) + 1)
    assert expired.value.status_code == 401


def test_admin_origin_configuration_is_normalized() -> None:
    settings = Settings(
        _env_file=None,
        admin_allowed_origins="HTTP://LOCALHOST:10100/, http://127.0.0.1:10100",
    )
    assert settings.admin_allowed_origin_list == [
        "http://localhost:10100",
        "http://127.0.0.1:10100",
    ]


def test_admin_signature_rejects_noncanonical_base64() -> None:
    import base64

    settings = admin_settings()
    token, _ = create_admin_session(settings)
    payload, signature = token.split(".")
    raw = base64.urlsafe_b64decode(signature + "=")
    aliases = 0
    for char in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_":
        altered = signature[:-1] + char
        if altered != signature and base64.urlsafe_b64decode(altered + "=") == raw:
            aliases += 1
            with pytest.raises(HTTPException):
                decode_admin_session(payload + "." + altered, settings)
    assert aliases == 3
