"""Device SRP helper for Cognito "remember this device".

Generates the password verifier sent to ``ConfirmDevice`` so the DroneMobile
Cognito user pool will remember this device. A remembered device lets token
refreshes succeed without falling back to a full (MFA) login, which is what
otherwise forces re-authentication every few hours.

This mirrors the AWS Cognito device SRP scheme (the same math used by
``pycognito`` / ``warrant``).
"""

from __future__ import annotations

import base64
import hashlib
import os

# 3072-bit group used by Cognito SRP.
_N_HEX = (
    "FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD1"
    "29024E088A67CC74020BBEA63B139B22514A08798E3404DD"
    "EF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245"
    "E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7ED"
    "EE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3D"
    "C2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F"
    "83655D23DCA3AD961C62F356208552BB9ED529077096966D"
    "670C354E4ABC9804F1746C08CA18217C32905E462E36CE3B"
    "E39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9"
    "DE2BCBF6955817183995497CEA956AE515D2261898FA0510"
    "15728E5A8AAAC42DAD33170D04507A33A85521ABDF1CBA64"
    "ECFB850458DBEF0A8AEA71575D060C7DB3970F85A6E1E4C7"
    "ABF5AE8CDB0933D71E8C94E04A25619DCEE3D2261AD2EE6B"
    "F12FFA06D98A0864D87602733EC86A64521F2B18177B200C"
    "BBE117577A615D6C770988C0BAD946E208E24FA074E5AB31"
    "43DB5BFCE0FD108E4B82D120A93AD2CAFFFFFFFFFFFFFFFF"
)
_BIG_N = int(_N_HEX, 16)
_G = 2


def _sha256_hex(data: bytes) -> str:
    """SHA-256 hex digest (always 64 chars)."""
    return hashlib.sha256(data).hexdigest()


def _pad_hex(value) -> str:
    """Hex-encode an int (or normalise a hex string) the Cognito way:
    even length, with a leading ``00`` byte when the top bit is set."""
    h = format(value, "x") if isinstance(value, int) else value
    if len(h) % 2 == 1:
        h = "0" + h
    elif h[0] in "89abcdefABCDEF":
        h = "00" + h
    return h


def generate_device_verifier(device_group_key: str, device_key: str):
    """Build the ConfirmDevice secret for a new device.

    Returns ``(device_password, {"PasswordVerifier": ..., "Salt": ...})``.
    The password must be kept (it identifies the remembered device); the
    verifier config is sent to Cognito's ``ConfirmDevice``.
    """
    device_password = base64.standard_b64encode(os.urandom(40)).decode("utf-8")
    full_password = f"{device_group_key}{device_key}:{device_password}"
    full_password_hash = _sha256_hex(full_password.encode("utf-8"))

    salt_hex = _pad_hex(int.from_bytes(os.urandom(16), "big"))
    x = int(_sha256_hex(bytes.fromhex(salt_hex + full_password_hash)), 16)
    verifier_hex = _pad_hex(pow(_G, x, _BIG_N))

    return device_password, {
        "PasswordVerifier": base64.standard_b64encode(
            bytes.fromhex(verifier_hex)
        ).decode("utf-8"),
        "Salt": base64.standard_b64encode(bytes.fromhex(salt_hex)).decode("utf-8"),
    }
