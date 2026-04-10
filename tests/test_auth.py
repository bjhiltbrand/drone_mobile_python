"""Tests for authentication module."""

from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest
import requests

from drone_mobile.auth import AuthenticationManager
from drone_mobile.exceptions import (
    AuthenticationError,
    InvalidCredentialsError,
    MFARequiredError,
    NetworkError,
)
from drone_mobile.models import AuthToken

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def auth_manager(tmp_path):
    """Create an AuthenticationManager with temporary token directory."""
    return AuthenticationManager("test@example.com", "password123", token_dir=tmp_path)


@pytest.fixture
def auth_manager_with_mfa(tmp_path):
    """AuthenticationManager that always returns '123456' as the MFA code."""
    return AuthenticationManager(
        "test@example.com",
        "password123",
        token_dir=tmp_path,
        mfa_callback=lambda _challenge: "123456",
    )


@pytest.fixture
def mock_auth_response():
    """Mock successful authentication response (no MFA)."""
    return {
        "AuthenticationResult": {
            "AccessToken": "access_token_123",
            "IdToken": "id_token_123",
            "RefreshToken": "refresh_token_123",
            "TokenType": "Bearer",
            "ExpiresIn": 3600,
        }
    }


@pytest.fixture
def sms_challenge_response():
    """Cognito response when SMS MFA is required."""
    return {
        "ChallengeName": "SMS_MFA",
        "Session": "session_abc",
        "ChallengeParameters": {
            "CODE_DELIVERY_DESTINATION": "+1***5678",
            "USER_ID_FOR_SRP": "test@example.com",
        },
    }


@pytest.fixture
def totp_challenge_response():
    """Cognito response when TOTP (authenticator app) MFA is required."""
    return {
        "ChallengeName": "SOFTWARE_TOKEN_MFA",
        "Session": "session_xyz",
        "ChallengeParameters": {},
    }


@pytest.fixture
def valid_token():
    """Create a valid AuthToken."""
    return AuthToken(
        access_token="access_token_123",
        id_token="id_token_123",
        refresh_token="refresh_token_123",
        token_type="Bearer",
        expires_at=datetime.now() + timedelta(hours=1),
    )


# ---------------------------------------------------------------------------
# Core authentication tests
# ---------------------------------------------------------------------------


class TestAuthenticationManager:
    """Tests for AuthenticationManager class."""

    def test_init(self, tmp_path):
        """Test initialization."""
        auth = AuthenticationManager("user@test.com", "pass", token_dir=tmp_path)
        assert auth.username == "user@test.com"
        assert auth.password == "pass"
        assert auth.token_dir == tmp_path
        assert auth._token is None
        assert auth.mfa_callback is None

    def test_init_creates_token_dir(self, tmp_path):
        """Token directory is created on instantiation, not at import time."""
        token_dir = tmp_path / "subdir" / "drone_mobile"
        assert not token_dir.exists()
        AuthenticationManager("u", "p", token_dir=token_dir)
        assert token_dir.exists()

    def test_init_with_mfa_callback(self, tmp_path):
        """Test initialization with an MFA callback."""
        cb = lambda _: "000000"  # noqa: E731
        auth = AuthenticationManager("u", "p", token_dir=tmp_path, mfa_callback=cb)
        assert auth.mfa_callback is cb

    @patch("drone_mobile.auth.requests.post")
    def test_authenticate_success(self, mock_post, auth_manager, mock_auth_response):
        """Test successful authentication (no MFA)."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_auth_response
        mock_post.return_value = mock_response

        token = auth_manager.authenticate()

        assert token.access_token == "access_token_123"
        assert token.id_token == "id_token_123"
        assert token.refresh_token == "refresh_token_123"
        assert token.token_type == "Bearer"
        assert not token.is_expired()

    @patch("drone_mobile.auth.requests.post")
    def test_authenticate_invalid_credentials(self, mock_post, auth_manager):
        """Test authentication with invalid credentials."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "__type": "NotAuthorizedException",
            "message": "Incorrect username or password",
        }
        mock_post.return_value = mock_response

        with pytest.raises(InvalidCredentialsError):
            auth_manager.authenticate()

    @patch("drone_mobile.auth.requests.post")
    def test_authenticate_network_error(self, mock_post, auth_manager):
        """Test authentication with network error."""
        mock_post.side_effect = requests.exceptions.ConnectionError("Network error")

        with pytest.raises(NetworkError):
            auth_manager.authenticate()

    @patch("drone_mobile.auth.requests.post")
    def test_refresh_token_success(self, mock_post, auth_manager, mock_auth_response, valid_token):
        """Test successful token refresh."""
        auth_manager._token = valid_token
        auth_manager._token.expires_at = datetime.now() - timedelta(minutes=1)  # Expired

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_auth_response
        mock_post.return_value = mock_response

        token = auth_manager._refresh_token()

        assert token.access_token == "access_token_123"
        assert not token.is_expired()

    @patch("drone_mobile.auth.requests.post")
    def test_refresh_token_expired_refresh(
        self, mock_post, auth_manager, mock_auth_response, valid_token
    ):
        """Test refresh when refresh token is expired."""
        auth_manager._token = valid_token
        auth_manager._token.expires_at = datetime.now() - timedelta(minutes=1)

        mock_response_401 = Mock()
        mock_response_401.status_code = 401

        mock_response_200 = Mock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = mock_auth_response

        mock_post.side_effect = [mock_response_401, mock_response_200]

        token = auth_manager._refresh_token()

        assert token.access_token == "access_token_123"
        assert mock_post.call_count == 2

    @patch("drone_mobile.auth.requests.post")
    def test_refresh_token_unexpected_response_shape(self, mock_post, auth_manager, valid_token):
        """Test that a 200 with no AuthenticationResult raises AuthenticationError."""
        auth_manager._token = valid_token
        auth_manager._token.expires_at = datetime.now() - timedelta(minutes=1)

        mock_response = Mock()
        mock_response.status_code = 200
        # Cognito returns 200 but with an unexpected body (e.g. maintenance page)
        mock_response.json.return_value = {"message": "Service temporarily unavailable"}
        mock_post.return_value = mock_response

        with pytest.raises(AuthenticationError, match="Unexpected token refresh response shape"):
            auth_manager._refresh_token()

    def test_save_and_load_token(self, auth_manager, valid_token):
        """Test saving and loading token from file."""
        auth_manager._save_token(valid_token)
        loaded_token = auth_manager._load_token()

        assert loaded_token.access_token == valid_token.access_token
        assert loaded_token.id_token == valid_token.id_token
        assert loaded_token.refresh_token == valid_token.refresh_token
        assert loaded_token.token_type == valid_token.token_type

    def test_load_token_nonexistent(self, auth_manager):
        """Test loading token when file doesn't exist."""
        token = auth_manager._load_token()
        assert token is None

    def test_get_auth_headers(self, auth_manager, valid_token):
        """Test getting authorization headers."""
        auth_manager._token = valid_token

        headers = auth_manager.get_auth_headers()

        assert "Authorization" in headers
        assert headers["Authorization"] == f"Bearer {valid_token.id_token}"
        assert headers["Content-Type"] == "application/json"

    def test_invalidate_token(self, auth_manager, valid_token):
        """Test token invalidation."""
        auth_manager._token = valid_token
        auth_manager._save_token(valid_token)

        auth_manager.invalidate_token()

        assert auth_manager._token is None
        assert not auth_manager.token_file.exists()


# ---------------------------------------------------------------------------
# MFA challenge tests
# ---------------------------------------------------------------------------


class TestMFAChallenge:
    """Tests for the MFA / 2-factor authentication flow."""

    # --- SMS_MFA ---

    @patch("drone_mobile.auth.requests.post")
    def test_sms_mfa_raises_when_no_callback(self, mock_post, auth_manager, sms_challenge_response):
        """MFARequiredError is raised if no callback is configured."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = sms_challenge_response
        mock_post.return_value = mock_response

        with pytest.raises(MFARequiredError) as exc_info:
            auth_manager.authenticate()

        assert exc_info.value.challenge_name == "SMS_MFA"

    @patch("drone_mobile.auth.requests.post")
    def test_sms_mfa_success(
        self,
        mock_post,
        auth_manager_with_mfa,
        sms_challenge_response,
        mock_auth_response,
    ):
        """Full SMS MFA flow completes successfully."""
        # First call: InitiateAuth → SMS challenge
        initiate_resp = Mock()
        initiate_resp.status_code = 200
        initiate_resp.json.return_value = sms_challenge_response

        # Second call: RespondToAuthChallenge → tokens
        challenge_resp = Mock()
        challenge_resp.status_code = 200
        challenge_resp.json.return_value = mock_auth_response

        mock_post.side_effect = [initiate_resp, challenge_resp]

        token = auth_manager_with_mfa.authenticate()

        assert token.access_token == "access_token_123"
        assert not token.is_expired()
        assert mock_post.call_count == 2

        # Verify the second call used the correct challenge payload
        second_call_payload = mock_post.call_args_list[1].kwargs["json"]
        assert second_call_payload["ChallengeName"] == "SMS_MFA"
        assert second_call_payload["Session"] == "session_abc"
        assert second_call_payload["ChallengeResponses"]["SMS_MFA_CODE"] == "123456"
        assert second_call_payload["ChallengeResponses"]["USERNAME"] == "test@example.com"

    @patch("drone_mobile.auth.requests.post")
    def test_sms_mfa_wrong_code(self, mock_post, auth_manager_with_mfa, sms_challenge_response):
        """CodeMismatchException from Cognito surfaces as AuthenticationError."""
        initiate_resp = Mock()
        initiate_resp.status_code = 200
        initiate_resp.json.return_value = sms_challenge_response

        challenge_resp = Mock()
        challenge_resp.status_code = 400
        challenge_resp.json.return_value = {
            "__type": "CodeMismatchException",
            "message": "Invalid code provided, please request a code again.",
        }

        mock_post.side_effect = [initiate_resp, challenge_resp]

        with pytest.raises(AuthenticationError, match="Incorrect MFA code"):
            auth_manager_with_mfa.authenticate()

    @patch("drone_mobile.auth.requests.post")
    def test_sms_mfa_expired_code(self, mock_post, auth_manager_with_mfa, sms_challenge_response):
        """ExpiredCodeException surfaces as AuthenticationError."""
        initiate_resp = Mock()
        initiate_resp.status_code = 200
        initiate_resp.json.return_value = sms_challenge_response

        challenge_resp = Mock()
        challenge_resp.status_code = 400
        challenge_resp.json.return_value = {
            "__type": "ExpiredCodeException",
            "message": "Your software token has expired.",
        }

        mock_post.side_effect = [initiate_resp, challenge_resp]

        with pytest.raises(AuthenticationError, match="expired"):
            auth_manager_with_mfa.authenticate()

    @patch("drone_mobile.auth.requests.post")
    def test_sms_mfa_network_error_on_challenge(
        self, mock_post, auth_manager_with_mfa, sms_challenge_response
    ):
        """NetworkError is raised when the RespondToAuthChallenge call fails."""
        initiate_resp = Mock()
        initiate_resp.status_code = 200
        initiate_resp.json.return_value = sms_challenge_response

        mock_post.side_effect = [
            initiate_resp,
            requests.exceptions.ConnectionError("timeout"),
        ]

        with pytest.raises(NetworkError):
            auth_manager_with_mfa.authenticate()

    # --- SOFTWARE_TOKEN_MFA (TOTP) ---

    @patch("drone_mobile.auth.requests.post")
    def test_totp_mfa_success(
        self,
        mock_post,
        auth_manager_with_mfa,
        totp_challenge_response,
        mock_auth_response,
    ):
        """Full TOTP MFA flow completes successfully."""
        initiate_resp = Mock()
        initiate_resp.status_code = 200
        initiate_resp.json.return_value = totp_challenge_response

        challenge_resp = Mock()
        challenge_resp.status_code = 200
        challenge_resp.json.return_value = mock_auth_response

        mock_post.side_effect = [initiate_resp, challenge_resp]

        token = auth_manager_with_mfa.authenticate()

        assert not token.is_expired()

        second_call_payload = mock_post.call_args_list[1].kwargs["json"]
        assert second_call_payload["ChallengeName"] == "SOFTWARE_TOKEN_MFA"
        # TOTP uses a different key name
        assert second_call_payload["ChallengeResponses"]["SOFTWARE_TOKEN_MFA_CODE"] == "123456"

    @patch("drone_mobile.auth.requests.post")
    def test_totp_mfa_raises_when_no_callback(
        self, mock_post, auth_manager, totp_challenge_response
    ):
        """MFARequiredError is raised for TOTP challenges when no callback is set."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = totp_challenge_response
        mock_post.return_value = mock_response

        with pytest.raises(MFARequiredError) as exc_info:
            auth_manager.authenticate()

        assert exc_info.value.challenge_name == "SOFTWARE_TOKEN_MFA"

    # --- Unsupported challenge ---

    @patch("drone_mobile.auth.requests.post")
    def test_unsupported_challenge_raises(self, mock_post, auth_manager_with_mfa):
        """AuthenticationError is raised for challenges the library doesn't handle."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ChallengeName": "MFA_SETUP",
            "Session": "sess",
            "ChallengeParameters": {},
        }
        mock_post.return_value = mock_response

        with pytest.raises(AuthenticationError, match="Unsupported Cognito challenge"):
            auth_manager_with_mfa.authenticate()

    # --- Empty code guard ---

    @patch("drone_mobile.auth.requests.post")
    def test_empty_mfa_code_raises(self, mock_post, tmp_path, sms_challenge_response):
        """AuthenticationError is raised when the callback returns an empty string."""
        auth = AuthenticationManager("u", "p", token_dir=tmp_path, mfa_callback=lambda _: "   ")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = sms_challenge_response
        mock_post.return_value = mock_response

        with pytest.raises(AuthenticationError, match="empty code"):
            auth.authenticate()

    # --- OTP length validation ---

    @pytest.mark.parametrize("bad_code", ["12345", "1234567", "12345a", "abc123"])
    @patch("drone_mobile.auth.requests.post")
    def test_mfa_code_wrong_length_raises(
        self, mock_post, tmp_path, sms_challenge_response, bad_code
    ):
        """AuthenticationError is raised when the OTP is not exactly 6 digits."""
        auth = AuthenticationManager("u", "p", token_dir=tmp_path, mfa_callback=lambda _: bad_code)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = sms_challenge_response
        mock_post.return_value = mock_response

        with pytest.raises(AuthenticationError, match="exactly 6 digits"):
            auth.authenticate()

    @patch("drone_mobile.auth.requests.post")
    def test_mfa_code_exactly_6_digits_accepted(
        self, mock_post, tmp_path, sms_challenge_response, mock_auth_response
    ):
        """A correctly formed 6-digit OTP passes validation and reaches Cognito."""
        auth = AuthenticationManager("u", "p", token_dir=tmp_path, mfa_callback=lambda _: "654321")

        initiate_resp = Mock()
        initiate_resp.status_code = 200
        initiate_resp.json.return_value = sms_challenge_response

        challenge_resp = Mock()
        challenge_resp.status_code = 200
        challenge_resp.json.return_value = mock_auth_response

        mock_post.side_effect = [initiate_resp, challenge_resp]

        token = auth.authenticate()
        assert not token.is_expired()

    # --- Missing Session guard ---

    @patch("drone_mobile.auth.requests.post")
    def test_missing_session_token_raises(self, mock_post, auth_manager_with_mfa):
        """AuthenticationError is raised when Cognito omits the Session token."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ChallengeName": "SMS_MFA",
            # Session key intentionally absent
            "ChallengeParameters": {},
        }
        mock_post.return_value = mock_response

        with pytest.raises(AuthenticationError, match="missing a Session token"):
            auth_manager_with_mfa.authenticate()

    # --- Callback receives challenge name ---

    @patch("drone_mobile.auth.requests.post")
    def test_callback_receives_challenge_name(
        self, mock_post, tmp_path, sms_challenge_response, mock_auth_response
    ):
        """The mfa_callback is called with the exact Cognito challenge name."""
        received: list[str] = []

        def capturing_callback(challenge_name: str) -> str:
            received.append(challenge_name)
            return "654321"

        auth = AuthenticationManager("u", "p", token_dir=tmp_path, mfa_callback=capturing_callback)

        initiate_resp = Mock()
        initiate_resp.status_code = 200
        initiate_resp.json.return_value = sms_challenge_response

        challenge_resp = Mock()
        challenge_resp.status_code = 200
        challenge_resp.json.return_value = mock_auth_response

        mock_post.side_effect = [initiate_resp, challenge_resp]

        auth.authenticate()

        assert received == ["SMS_MFA"]


# ---------------------------------------------------------------------------
# AuthToken model tests
# ---------------------------------------------------------------------------


class TestAuthToken:
    """Tests for AuthToken model."""

    def test_is_expired_false(self):
        """Test token that is not expired."""
        token = AuthToken(
            access_token="test",
            id_token="test",
            refresh_token="test",
            token_type="Bearer",
            expires_at=datetime.now() + timedelta(hours=1),
        )
        assert not token.is_expired()

    def test_is_expired_true(self):
        """Test token that is expired."""
        token = AuthToken(
            access_token="test",
            id_token="test",
            refresh_token="test",
            token_type="Bearer",
            expires_at=datetime.now() - timedelta(minutes=1),
        )
        assert token.is_expired()

    def test_to_dict(self, valid_token):
        """Test converting token to dictionary."""
        token_dict = valid_token.to_dict()

        assert token_dict["access_token"] == valid_token.access_token
        assert token_dict["id_token"] == valid_token.id_token
        assert token_dict["refresh_token"] == valid_token.refresh_token
        assert token_dict["token_type"] == valid_token.token_type
        assert "expires_at" in token_dict

    def test_from_dict(self, valid_token):
        """Test creating token from dictionary."""
        token_dict = valid_token.to_dict()
        loaded_token = AuthToken.from_dict(token_dict)

        assert loaded_token.access_token == valid_token.access_token
        assert loaded_token.id_token == valid_token.id_token
        assert loaded_token.refresh_token == valid_token.refresh_token
        assert loaded_token.token_type == valid_token.token_type
