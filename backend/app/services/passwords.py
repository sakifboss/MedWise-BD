"""Doctor passwords: hashing (scrypt, standard library) and the password rules.

Hash format: scrypt$<N>$<r>$<p>$<salt base64>$<hash base64>. The parameters are stored with each
hash, so they can be raised later (or the scheme moved to argon2id) and old hashes still verify;
needs_rehash() says when a hash should be replaced at the next successful login.

Parameters: N=2^14, r=8, p=5, one of the OWASP-recommended scrypt settings (about 16 MB of memory
per hash, so logins stay rate-limited). 16-byte random salt per password, 32-byte key, compared in
constant time.

Rules: at least 10 characters and not a common password (app/core/common_passwords.txt, from
SecLists); no other composition rules. Nothing here ever logs a password.
"""

import base64
import hashlib
import hmac
import secrets
from functools import lru_cache
from pathlib import Path

SCHEME = "scrypt"
N, R, P = 2**14, 8, 5
SALT_BYTES = 16
KEY_BYTES = 32
MAX_MEMORY = 64 * 1024 * 1024  # above 128 * r * N (16 MB); hashlib refuses more than maxmem

MIN_LENGTH = 10
MAX_LENGTH = 128  # long enough for passphrases, short enough to keep hashing cheap
COMMON_PASSWORDS = Path(__file__).resolve().parents[1] / "core" / "common_passwords.txt"


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _derive(password: str, salt: bytes, n: int, r: int, p: int, length: int) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=n, r=r, p=p, maxmem=MAX_MEMORY, dklen=length
    )


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(SALT_BYTES)
    key = _derive(password, salt, N, R, P, KEY_BYTES)
    return f"{SCHEME}${N}${R}${P}${_b64(salt)}${_b64(key)}"


def verify_password(password: str, stored: str) -> bool:
    """True when the password matches the stored hash (any supported parameters)."""
    try:
        scheme, n, r, p, salt, key = stored.split("$")
        if scheme != SCHEME:
            return False
        expected = base64.b64decode(key)
        actual = _derive(password, base64.b64decode(salt), int(n), int(r), int(p), len(expected))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


def needs_rehash(stored: str) -> bool:
    """True when the hash was made with other (older) parameters than today's."""
    parts = stored.split("$")
    return len(parts) != 6 or parts[:4] != [SCHEME, str(N), str(R), str(P)]


# A hash of a random password: verified when the email is unknown, so a login with an unknown
# email takes as long as one with a wrong password (the response time reveals nothing).
@lru_cache(maxsize=1)
def dummy_hash() -> str:
    return hash_password(secrets.token_urlsafe(16))


@lru_cache(maxsize=1)
def _common_passwords() -> frozenset[str]:
    lines = COMMON_PASSWORDS.read_text(encoding="utf-8").splitlines()
    return frozenset(line for line in lines if line and not line.startswith("#"))


def password_problem(password: str, email: str = "", name: str = "") -> str | None:
    """Why a new password is not allowed (an error code), or None when it is fine."""
    if len(password) < MIN_LENGTH:
        return "password_too_short"
    if len(password) > MAX_LENGTH:
        return "password_too_long"
    lowered = password.casefold()
    if lowered in _common_passwords():
        return "password_common"
    personal = {email.casefold(), email.split("@")[0].casefold(), name.casefold().replace(" ", "")}
    if lowered.replace(" ", "") in {p for p in personal if p}:
        return "password_personal"
    return None
