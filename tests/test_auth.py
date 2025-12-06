"""Tests for authentication module."""

from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest
import requests

from drone_mobile.auth import AuthenticationManager
from drone_mobile.exceptions import InvalidCredentialsError, NetworkError
from drone_mobile.models import AuthToken


@pytest.fixture
def auth_manager(tmp_path):
    """Create an AuthenticationManager with temporary token directory."""
    return AuthenticationManager("test@example.com", "password123", token_dir=tmp_path)


@pytest.fixture
def mock_auth_response():
    """Mock successful authentication response."""
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
def valid_token():
    """Create a valid AuthToken."""
    return AuthToken(
        access_token="access_token_123",
        id_token="id_token_123",
        refresh_token="refresh_token_123",
        token_type="Bearer",
        expires_at=datetime.now() + timedelta(hours=1),
    )


class TestAuthenticationManager:
    """Tests for AuthenticationManager class."""

    def test_init(self, tmp_path):
        """Test initialization."""
        auth = AuthenticationManager("user@test.com", "pass", token_dir=tmp_path)
        assert auth.username == "user@test.com"
        assert auth.password == "pass"
        assert auth.token_dir == tmp_path
        assert auth._token is None

    @patch("drone_mobile.auth.requests.post")
    def test_authenticate_success(self, mock_post, auth_manager, mock_auth_response):
        """Test successful authentication."""
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

        # First call returns 401 (refresh token expired)
        mock_response_401 = Mock()
        mock_response_401.status_code = 401

        # Second call succeeds with new auth
        mock_response_200 = Mock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = mock_auth_response

        mock_post.side_effect = [mock_response_401, mock_response_200]

        token = auth_manager._refresh_token()

        assert token.access_token == "access_token_123"
        assert mock_post.call_count == 2

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
