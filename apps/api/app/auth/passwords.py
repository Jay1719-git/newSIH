from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

_SCRYPT_N = 2**15
_SCRYPT_R = 8
_SCRYPT_P = 1
_KEY_LENGTH = 64


def hash_password(password: str) -> str:
    if len(password) < 12 or len(password) > 1024:
        raise ValueError("Password must be between 12 and 1024 characters.")
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_KEY_LENGTH,
        maxmem=64 * 1024 * 1024,
    )
    return "scrypt${}${}${}${}".format(
        _SCRYPT_N,
        _SCRYPT_R,
        _SCRYPT_P,
        base64.urlsafe_b64encode(salt + derived).decode("ascii"),
    )


def verify_password(password: str, encoded: str | None) -> bool:
    if not encoded:
        # Burn comparable work for unknown accounts to reduce email enumeration timing.
        hashlib.scrypt(
            password.encode("utf-8"),
            salt=b"weave-auth-dummy!",
            n=_SCRYPT_N,
            r=_SCRYPT_R,
            p=_SCRYPT_P,
            dklen=_KEY_LENGTH,
            maxmem=64 * 1024 * 1024,
        )
        return False
    try:
        algorithm, n_value, r_value, p_value, payload = encoded.split("$", 4)
        if algorithm != "scrypt":
            return False
        n, r, p = int(n_value), int(r_value), int(p_value)
        if (n, r, p) != (_SCRYPT_N, _SCRYPT_R, _SCRYPT_P):
            return False
        decoded = base64.urlsafe_b64decode(payload.encode("ascii"))
        salt, expected = decoded[:16], decoded[16:]
        if len(salt) != 16 or len(expected) != _KEY_LENGTH:
            return False
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=n,
            r=r,
            p=p,
            dklen=_KEY_LENGTH,
            maxmem=64 * 1024 * 1024,
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError, UnicodeError):
        return False
