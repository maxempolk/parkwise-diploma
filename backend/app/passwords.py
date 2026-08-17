"""Password hashing helpers for the administrator account."""

from __future__ import annotations

from base64 import urlsafe_b64decode, urlsafe_b64encode
from getpass import getpass
from hashlib import pbkdf2_hmac
from hmac import compare_digest
from secrets import token_bytes

ALGORITHM = "pbkdf2_sha256"
DEFAULT_ITERATIONS = 600_000
SALT_BYTES = 16


def _encode(value: bytes) -> str:
    return urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    return urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(password: str, *, iterations: int = DEFAULT_ITERATIONS, salt: bytes | None = None) -> str:
    if not password:
        raise ValueError("Password cannot be empty.")
    password_salt = salt or token_bytes(SALT_BYTES)
    digest = pbkdf2_hmac("sha256", password.encode("utf-8"), password_salt, iterations)
    return f"{ALGORITHM}${iterations}${_encode(password_salt)}${_encode(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations_text, salt_text, expected_text = encoded.split("$", maxsplit=3)
        if algorithm != ALGORITHM:
            return False
        iterations = int(iterations_text)
        if iterations <= 0:
            return False
        salt = _decode(salt_text)
        expected = _decode(expected_text)
    except (TypeError, ValueError):
        return False

    actual = pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return compare_digest(actual, expected)


def main() -> None:
    password = getpass("New administrator password: ")
    confirmation = getpass("Confirm administrator password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")
    print(hash_password(password))


if __name__ == "__main__":
    main()
