"""Signing Rx Pad QR codes (R4).

The browser sends only the SHA-256 of the prescription's QR payload (medicine lines and dates; no
patient details). The server answers sig = HMAC-SHA256(RX_SIGNING_SECRET,
"1|doctor_id|issued_at|hash") and stores nothing about the prescription. A QR proves who issued
it, not that the medicines or doses are right, and it can be copied.

If RX_SIGNING_SECRET changes, old QR codes still open but can no longer be checked.
"""

import base64
import hashlib
import hmac
import re

VERSION = "1"
HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
SIG_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")  # 32 bytes, base64url without padding


def _message(doctor_id: int, issued_at: int, payload_hash: str) -> bytes:
    return f"{VERSION}|{doctor_id}|{issued_at}|{payload_hash}".encode("ascii")


def sign(secret: str, doctor_id: int, issued_at: int, payload_hash: str) -> str:
    digest = hmac.new(
        secret.encode("utf-8"), _message(doctor_id, issued_at, payload_hash), hashlib.sha256
    )
    return base64.urlsafe_b64encode(digest.digest()).rstrip(b"=").decode("ascii")


def verify(secret: str, doctor_id: int, issued_at: int, payload_hash: str, sig: str) -> bool:
    """Constant-time check; False for any malformed input or a missing secret."""
    if not secret or not HASH_PATTERN.match(payload_hash) or not SIG_PATTERN.match(sig):
        return False
    expected = sign(secret, doctor_id, issued_at, payload_hash)
    return hmac.compare_digest(expected.encode("ascii"), sig.encode("ascii"))
