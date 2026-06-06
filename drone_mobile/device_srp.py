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
import datetime
import hashlib
import hmac
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


# ---------------------------------------------------------------------------
# Device SRP authentication (DEVICE_SRP_AUTH / DEVICE_PASSWORD_VERIFIER)
# ---------------------------------------------------------------------------
#
# Once a device is confirmed and "remembered", Cognito offers a DEVICE_SRP_AUTH
# challenge in place of MFA on subsequent logins. Answering it with the device
# password lets the integration re-authenticate unattended (no second factor),
# which is what keeps the connection alive after the refresh token expires.

# SRP-6a multiplier parameter: k = H(N | PAD(g)).
_K = int(_sha256_hex(bytes.fromhex("00" + _N_HEX + "0" + format(_G, "x"))), 16)
_DERIVED_KEY_INFO = b"Caldera Derived Key"


def _hex_hash(hex_str: str) -> str:
    """SHA-256 of the bytes a hex string represents, returned as hex."""
    return _sha256_hex(bytes.fromhex(hex_str))


def _hkdf(ikm: bytes, salt: bytes) -> bytes:
    """Cognito's HKDF: extract with ``salt``, expand to a 16-byte key."""
    prk = hmac.new(salt, ikm, hashlib.sha256).digest()
    return hmac.new(prk, _DERIVED_KEY_INFO + b"\x01", hashlib.sha256).digest()[:16]


def cognito_timestamp() -> str:
    """Timestamp in the exact format Cognito's SRP signature expects.

    e.g. ``"Tue Jun 5 09:08:07 UTC 2026"`` (English, UTC, day NOT zero-padded).
    The day must not be zero-padded or the signature check fails.
    """
    days = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
    months = (
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    )
    now = datetime.datetime.now(datetime.timezone.utc)
    return "%s %s %d %02d:%02d:%02d UTC %d" % (
        days[now.weekday()], months[now.month - 1], now.day,
        now.hour, now.minute, now.second, now.year,
    )


class DeviceSRP:
    """Client side of Cognito's device SRP exchange.

    Usage::

        srp = DeviceSRP(device_group_key, device_key, device_password)
        # answer DEVICE_SRP_AUTH with srp.srp_a, then for DEVICE_PASSWORD_VERIFIER:
        ts = cognito_timestamp()
        sig = srp.process_challenge(srp_b, salt, secret_block, ts)
    """

    def __init__(self, device_group_key: str, device_key: str, device_password: str):
        self.device_group_key = device_group_key
        self.device_key = device_key
        self.device_password = device_password
        self._small_a = int.from_bytes(os.urandom(128), "big") % _BIG_N
        self._large_a = pow(_G, self._small_a, _BIG_N)

    @property
    def srp_a(self) -> str:
        """Client public value ``A`` as hex (the ``SRP_A`` challenge parameter)."""
        return format(self._large_a, "x")

    def process_challenge(
        self, srp_b_hex: str, salt_hex: str, secret_block: str, timestamp: str
    ) -> str:
        """Compute ``PASSWORD_CLAIM_SIGNATURE`` for DEVICE_PASSWORD_VERIFIER.

        Args:
            srp_b_hex: server public value ``SRP_B`` (hex) from the challenge.
            salt_hex: ``SALT`` (hex) from the challenge.
            secret_block: ``SECRET_BLOCK`` (base64) from the challenge.
            timestamp: the value also returned as ``TIMESTAMP``; must come from
                :func:`cognito_timestamp` (the signature is over it).
        """
        big_b = int(srp_b_hex, 16)
        if big_b % _BIG_N == 0:
            raise ValueError("Bad server SRP_B value (B mod N == 0)")
        u = int(_hex_hash(_pad_hex(self._large_a) + _pad_hex(big_b)), 16)
        if u == 0:
            raise ValueError("Bad SRP U value (U == 0)")

        full_password = f"{self.device_group_key}{self.device_key}:{self.device_password}"
        full_password_hash = _sha256_hex(full_password.encode("utf-8"))
        x = int(_hex_hash(_pad_hex(salt_hex) + full_password_hash), 16)

        s = pow((big_b - _K * pow(_G, x, _BIG_N)) % _BIG_N, self._small_a + u * x, _BIG_N)
        key = _hkdf(bytes.fromhex(_pad_hex(s)), bytes.fromhex(_pad_hex(u)))

        message = (
            self.device_group_key.encode("utf-8")
            + self.device_key.encode("utf-8")
            + base64.standard_b64decode(secret_block)
            + timestamp.encode("utf-8")
        )
        return base64.standard_b64encode(
            hmac.new(key, message, hashlib.sha256).digest()
        ).decode("utf-8")
