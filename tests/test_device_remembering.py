"""Tests for Cognito device remembering (skip MFA on re-authentication).

Covers the three pieces of the fix:
  * the MFA challenge response echoes the pool's internal username
    (USER_ID_FOR_SRP), not the email alias, so the token can call ConfirmDevice;
  * a successful MFA login confirms + remembers the device and persists it;
  * a remembered device re-authenticates via DEVICE_SRP_AUTH with no MFA, and a
    rejected handshake clears the stale device.
"""

import base64
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from drone_mobile.auth import AuthenticationManager
from drone_mobile.device_srp import _BIG_N
from drone_mobile.exceptions import AuthenticationError
from drone_mobile.models import AuthToken


def _resp(status, payload):
    m = Mock()
    m.status_code = status
    m.json.return_value = payload
    return m


def _fail_mfa(_challenge):  # pragma: no cover - only called on failure
    raise AssertionError("mfa_callback must not be called for a remembered device")


@pytest.fixture
def totp_challenge_sub():
    """TOTP challenge where the internal username (sub) differs from the email."""
    return {
        "ChallengeName": "SOFTWARE_TOKEN_MFA",
        "Session": "sess-1",
        "ChallengeParameters": {"USER_ID_FOR_SRP": "sub-uuid-123"},
    }


@pytest.fixture
def tokens_with_device():
    return {
        "AuthenticationResult": {
            "AccessToken": "at",
            "IdToken": "it",
            "RefreshToken": "rt",
            "TokenType": "Bearer",
            "ExpiresIn": 3600,
            "NewDeviceMetadata": {
                "DeviceKey": "us-east-1_dev-1",
                "DeviceGroupKey": "-grp1",
            },
        }
    }


@pytest.fixture
def plain_tokens():
    return {
        "AuthenticationResult": {
            "AccessToken": "at",
            "IdToken": "it",
            "RefreshToken": "rt",
            "TokenType": "Bearer",
            "ExpiresIn": 3600,
        }
    }


# ---------------------------------------------------------------------------
# Username fix
# ---------------------------------------------------------------------------


@patch("drone_mobile.auth.requests.post")
def test_mfa_response_uses_internal_username(mock_post, tmp_path, totp_challenge_sub, plain_tokens):
    """The challenge response must echo USER_ID_FOR_SRP, not the email."""
    mock_post.side_effect = [_resp(200, totp_challenge_sub), _resp(200, plain_tokens)]
    auth = AuthenticationManager(
        "user@example.com", "pw", token_dir=tmp_path, mfa_callback=lambda _c: "123456"
    )

    auth.authenticate()

    challenge_payload = mock_post.call_args_list[1].kwargs["json"]
    assert challenge_payload["ChallengeResponses"]["USERNAME"] == "sub-uuid-123"


@patch("drone_mobile.auth.requests.post")
def test_mfa_username_falls_back_to_email(mock_post, tmp_path, plain_tokens):
    """When the pool omits USER_ID_FOR_SRP, fall back to the configured username."""
    challenge = {"ChallengeName": "SMS_MFA", "Session": "s", "ChallengeParameters": {}}
    mock_post.side_effect = [_resp(200, challenge), _resp(200, plain_tokens)]
    auth = AuthenticationManager(
        "user@example.com", "pw", token_dir=tmp_path, mfa_callback=lambda _c: "123456"
    )

    auth.authenticate()

    challenge_payload = mock_post.call_args_list[1].kwargs["json"]
    assert challenge_payload["ChallengeResponses"]["USERNAME"] == "user@example.com"


# ---------------------------------------------------------------------------
# Confirm + remember
# ---------------------------------------------------------------------------


@patch("drone_mobile.auth.requests.post")
def test_device_confirmed_and_remembered(
    mock_post, tmp_path, totp_challenge_sub, tokens_with_device
):
    mock_post.side_effect = [
        _resp(200, totp_challenge_sub),  # InitiateAuth -> challenge
        _resp(200, tokens_with_device),  # RespondToAuthChallenge -> tokens + device
        _resp(200, {"UserConfirmationNecessary": True}),  # ConfirmDevice
        _resp(200, {}),  # UpdateDeviceStatus
    ]
    auth = AuthenticationManager(
        "user@example.com", "pw", token_dir=tmp_path, mfa_callback=lambda _c: "123456"
    )

    auth.authenticate()

    # Persisted device file with the key, group key and a generated password.
    assert auth.device_file.exists()
    saved = json.loads(auth.device_file.read_text())
    assert saved["DeviceKey"] == "us-east-1_dev-1"
    assert saved["DeviceGroupKey"] == "-grp1"
    assert saved["DevicePassword"]

    # ConfirmDevice carried the verifier and targeted the right Cognito action.
    confirm = mock_post.call_args_list[2]
    assert confirm.kwargs["json"]["DeviceKey"] == "us-east-1_dev-1"
    assert "DeviceSecretVerifierConfig" in confirm.kwargs["json"]
    assert confirm.kwargs["headers"]["X-Amz-Target"].endswith("ConfirmDevice")

    update = mock_post.call_args_list[3]
    assert update.kwargs["json"]["DeviceRememberedStatus"] == "remembered"
    assert update.kwargs["headers"]["X-Amz-Target"].endswith("UpdateDeviceStatus")


@patch("drone_mobile.auth.requests.post")
def test_confirm_failure_does_not_break_login(
    mock_post, tmp_path, totp_challenge_sub, tokens_with_device
):
    """A ConfirmDevice rejection is swallowed: the user still gets logged in."""
    mock_post.side_effect = [
        _resp(200, totp_challenge_sub),
        _resp(200, tokens_with_device),
        _resp(400, {"__type": "InvalidParameterException", "message": "Invalid device key given."}),
    ]
    auth = AuthenticationManager(
        "user@example.com", "pw", token_dir=tmp_path, mfa_callback=lambda _c: "123456"
    )

    token = auth.authenticate()

    assert token.access_token == "at"
    assert not auth.device_file.exists()


# ---------------------------------------------------------------------------
# Device SRP re-auth (no MFA)
# ---------------------------------------------------------------------------


def _seed_device(auth):
    # Computed at runtime from obvious plaintext so no secret-looking literal
    # ends up in the source (the value is meaningless test data).
    auth._device = {
        "DeviceKey": "us-east-1_dev-1",
        "DeviceGroupKey": "-grp1",
        "DevicePassword": base64.b64encode(b"unit-test-device-password").decode(),
    }
    auth._save_device()


@patch("drone_mobile.auth.requests.post")
def test_new_auth_sends_device_key(mock_post, tmp_path, plain_tokens):
    """When a device is remembered, InitiateAuth carries DEVICE_KEY."""
    # No challenge here; return tokens directly so we only assert the request shape.
    auth = AuthenticationManager("user@example.com", "pw", token_dir=tmp_path)
    _seed_device(auth)
    mock_post.return_value = _resp(200, plain_tokens)

    auth.authenticate(force_refresh=True)

    init_payload = mock_post.call_args_list[0].kwargs["json"]
    assert init_payload["AuthParameters"]["DEVICE_KEY"] == "us-east-1_dev-1"


@patch("drone_mobile.auth.requests.post")
def test_device_srp_login_skips_mfa(mock_post, tmp_path, plain_tokens):
    auth = AuthenticationManager(
        "user@example.com", "pw", token_dir=tmp_path, mfa_callback=_fail_mfa
    )
    _seed_device(auth)

    device_srp = {
        "ChallengeName": "DEVICE_SRP_AUTH",
        "Session": "sess-d",
        "ChallengeParameters": {"USERNAME": "sub-uuid-123"},
    }
    password_verifier = {
        "ChallengeName": "DEVICE_PASSWORD_VERIFIER",
        "Session": "sess-d2",
        "ChallengeParameters": {
            "SRP_B": format((_BIG_N // 2) + 1234567, "x"),
            "SALT": "0a1b2c3d",
            "SECRET_BLOCK": base64.b64encode(b"unit-test-secret-block").decode(),
        },
    }
    mock_post.side_effect = [
        _resp(200, device_srp),  # InitiateAuth -> DEVICE_SRP_AUTH
        _resp(200, password_verifier),  # DEVICE_SRP_AUTH -> DEVICE_PASSWORD_VERIFIER
        _resp(200, plain_tokens),  # DEVICE_PASSWORD_VERIFIER -> tokens
    ]

    token = auth.authenticate(force_refresh=True)

    assert token.access_token == "at"
    assert mock_post.call_args_list[1].kwargs["json"]["ChallengeName"] == "DEVICE_SRP_AUTH"
    final = mock_post.call_args_list[2].kwargs["json"]
    assert final["ChallengeName"] == "DEVICE_PASSWORD_VERIFIER"
    assert final["ChallengeResponses"]["DEVICE_KEY"] == "us-east-1_dev-1"
    assert "PASSWORD_CLAIM_SIGNATURE" in final["ChallengeResponses"]
    assert auth.device_file.exists()  # still remembered


@patch("drone_mobile.auth.requests.post")
def test_device_srp_failure_clears_device(mock_post, tmp_path):
    auth = AuthenticationManager(
        "user@example.com", "pw", token_dir=tmp_path, mfa_callback=lambda _c: "123456"
    )
    _seed_device(auth)
    assert auth.device_file.exists()

    device_srp = {
        "ChallengeName": "DEVICE_SRP_AUTH",
        "Session": "s",
        "ChallengeParameters": {"USERNAME": "sub"},
    }
    mock_post.side_effect = [
        _resp(200, device_srp),  # InitiateAuth -> DEVICE_SRP_AUTH
        _resp(400, {"__type": "NotAuthorizedException", "message": "Device not found"}),
    ]

    with pytest.raises(AuthenticationError):
        auth.authenticate(force_refresh=True)

    assert not auth.device_file.exists()
    assert auth._device is None


# ---------------------------------------------------------------------------
# Refresh carries the device key
# ---------------------------------------------------------------------------


@patch("drone_mobile.auth.requests.post")
def test_refresh_includes_device_key(mock_post, tmp_path):
    auth = AuthenticationManager("user@example.com", "pw", token_dir=tmp_path)
    _seed_device(auth)
    auth._token = AuthToken(
        access_token="at",
        id_token="it",
        refresh_token="rt",
        token_type="Bearer",
        expires_at=datetime.now() - timedelta(minutes=1),
    )
    mock_post.return_value = _resp(
        200,
        {
            "AuthenticationResult": {
                "AccessToken": "at2",
                "IdToken": "it2",
                "TokenType": "Bearer",
                "ExpiresIn": 3600,
            }
        },
    )

    auth._refresh_token()

    payload = mock_post.call_args_list[0].kwargs["json"]
    assert payload["AuthParameters"]["REFRESH_TOKEN"] == "rt"
    assert payload["AuthParameters"]["DEVICE_KEY"] == "us-east-1_dev-1"
