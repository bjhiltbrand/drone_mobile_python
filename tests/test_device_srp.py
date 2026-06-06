"""Tests for the device SRP helpers (Cognito "remember this device").

The headline test is a full SRP round trip: we register a device verifier the
same way ``ConfirmDevice`` would, then play the role of the Cognito server and
check that :class:`DeviceSRP` derives the identical session key (and therefore
the identical ``PASSWORD_CLAIM_SIGNATURE``). This proves the client side of the
exchange is correct against the SRP protocol itself, with no external reference
implementation and no network.
"""

import base64
import hashlib
import hmac
import os
import re

import pytest

from drone_mobile.device_srp import (
    _BIG_N,
    _G,
    _K,
    _hex_hash,
    _hkdf,
    _pad_hex,
    DeviceSRP,
    cognito_timestamp,
    generate_device_verifier,
)

DGK = "-GROUPKEY1"
DK = "us-east-1_11111111-2222-3333-4444-555555555555"


# ---------------------------------------------------------------------------
# generate_device_verifier (ConfirmDevice registration secret)
# ---------------------------------------------------------------------------


class TestGenerateDeviceVerifier:
    def test_shape(self):
        password, config = generate_device_verifier(DGK, DK)
        assert isinstance(password, str) and password
        assert set(config) == {"PasswordVerifier", "Salt"}
        verifier = base64.standard_b64decode(config["PasswordVerifier"])
        salt = base64.standard_b64decode(config["Salt"])
        # 3072-bit modulus -> 384-byte verifier (385 with the leading-zero pad).
        assert len(verifier) in (384, 385)
        assert len(salt) in (16, 17)

    def test_randomized(self):
        _, a = generate_device_verifier(DGK, DK)
        _, b = generate_device_verifier(DGK, DK)
        assert a["PasswordVerifier"] != b["PasswordVerifier"]
        assert a["Salt"] != b["Salt"]


# ---------------------------------------------------------------------------
# cognito_timestamp
# ---------------------------------------------------------------------------


class TestCognitoTimestamp:
    def test_format(self):
        ts = cognito_timestamp()
        # e.g. "Tue Jun 5 09:08:07 UTC 2026" - day is NOT zero-padded.
        assert re.match(
            r"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun) "
            r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) "
            r"\d{1,2} \d{2}:\d{2}:\d{2} UTC \d{4}$",
            ts,
        ), ts

    def test_day_not_zero_padded(self):
        # The day field must never carry a leading zero (Cognito rejects the
        # signature otherwise). Verify the token between the month and time.
        day_field = cognito_timestamp().split()[2]
        assert not (len(day_field) == 2 and day_field[0] == "0")


# ---------------------------------------------------------------------------
# DeviceSRP
# ---------------------------------------------------------------------------


class TestDeviceSRP:
    def test_srp_a_is_valid_public_value(self):
        srp = DeviceSRP(DGK, DK, "device-password")
        a = int(srp.srp_a, 16)
        assert 0 < a < _BIG_N

    def test_roundtrip_matches_server(self):
        """Client derives the same signature the Cognito server would expect."""
        # 1. Register the device verifier (what ConfirmDevice stores).
        device_password, config = generate_device_verifier(DGK, DK)
        salt_hex = base64.standard_b64decode(config["Salt"]).hex()
        verifier = int.from_bytes(base64.standard_b64decode(config["PasswordVerifier"]), "big")

        # 2. Client starts the device SRP exchange.
        srp = DeviceSRP(DGK, DK, device_password)
        big_a = int(srp.srp_a, 16)

        # 3. Server picks a random b and sends B = (k*v + g^b) mod N.
        b = int.from_bytes(os.urandom(32), "big") % _BIG_N
        big_b = (_K * verifier + pow(_G, b, _BIG_N)) % _BIG_N
        secret_block = base64.standard_b64encode(os.urandom(64)).decode()
        timestamp = cognito_timestamp()

        signature = srp.process_challenge(format(big_b, "x"), salt_hex, secret_block, timestamp)

        # 4. Server independently derives S = (A * v^u)^b and the signature.
        u = int(_hex_hash(_pad_hex(big_a) + _pad_hex(big_b)), 16)
        s_server = pow((big_a * pow(verifier, u, _BIG_N)) % _BIG_N, b, _BIG_N)
        key_server = _hkdf(bytes.fromhex(_pad_hex(s_server)), bytes.fromhex(_pad_hex(u)))
        message = (
            DGK.encode()
            + DK.encode()
            + base64.standard_b64decode(secret_block)
            + timestamp.encode()
        )
        expected = base64.standard_b64encode(
            hmac.new(key_server, message, hashlib.sha256).digest()
        ).decode()

        assert signature == expected

    def test_rejects_zero_b(self):
        srp = DeviceSRP(DGK, DK, "device-password")
        with pytest.raises(ValueError, match="B mod N"):
            srp.process_challenge(
                format(_BIG_N, "x"),  # B == N -> B mod N == 0
                "0a1b",
                base64.standard_b64encode(b"x").decode(),
                cognito_timestamp(),
            )

    def test_signature_is_32_byte_hmac(self):
        srp = DeviceSRP(DGK, DK, "device-password")
        sig = srp.process_challenge(
            format((_BIG_N // 3) + 7, "x"),
            "0a1b2c3d",
            base64.standard_b64encode(os.urandom(48)).decode(),
            cognito_timestamp(),
        )
        assert len(base64.standard_b64decode(sig)) == 32
