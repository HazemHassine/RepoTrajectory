#!/usr/bin/env python3
"""Configure local admin credentials without persisting or echoing the plaintext password."""

import base64
import getpass
import hashlib
import os
import secrets
import sys
import tempfile
from pathlib import Path

PBKDF2_ITERATIONS = 600_000


def encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    return f"pbkdf2_sha256:{PBKDF2_ITERATIONS}:{encode(salt)}:{encode(digest)}"


def update_values(path: Path, values: dict[str, str]) -> None:
    lines = path.read_text().splitlines() if path.exists() else []
    written: set[str] = set()
    output: list[str] = []
    for line in lines:
        key = line.split("=", 1)[0] if "=" in line and not line.startswith("#") else None
        if key in values:
            output.append(f"{key}={values[key]}")
            written.add(key)
        else:
            output.append(line)
    if output and output[-1]:
        output.append("")
    for key, value in values.items():
        if key not in written:
            output.append(f"{key}={value}")

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".env-admin-", dir=path.parent)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w") as handle:
            handle.write("\n".join(output).rstrip() + "\n")
        os.replace(temporary_name, path)
        os.chmod(path, 0o600)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def main() -> int:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else ".env").resolve()
    password = getpass.getpass("Admin password: ")
    if not 12 <= len(password) <= 256:
        print("Password must contain between 12 and 256 characters.", file=sys.stderr)
        return 2
    confirmation = getpass.getpass("Confirm admin password: ")
    if not secrets.compare_digest(password, confirmation):
        print("Passwords do not match.", file=sys.stderr)
        return 2

    update_values(
        path,
        {
            "ADMIN_USERNAME": "admin",
            "ADMIN_PASSWORD_HASH": password_hash(password),
            "ADMIN_SESSION_SECRET": secrets.token_urlsafe(48),
        },
    )
    password = ""
    confirmation = ""
    print("Admin credentials updated. The plaintext password was not stored or printed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
