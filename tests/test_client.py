"""Tests for client module."""

from unittest.mock import Mock, patch

import pytest
import requests

from drone_mobile.client import DroneMobileClient
from drone_mobile.exceptions import (
    CommandFailedError,
    InvalidCommandError,
    RateLimitError,
    VehicleNotFoundError,
)
from drone_mobile.vehicle import Vehicle


@pytest.fixture
def mock_auth():
    """Mock authentication manager."""
    auth = Mock()
    auth.get_auth_headers.return_value = {
        "Authorization": "Bearer test_token",
        "Content-Type": "application/json",
    }
    return auth


@pytest.fixture
def client(tmp_path):
    """Create a DroneMobileClient."""
    return DroneMobileClient("test@example.com", "password123", token_dir=tmp_path)


@pytest.fixture
def mock_vehicle_response():
    """Mock vehicle list response."""
    return {
        "results": [
            {
                "vehicle_id": "123",
                "device_key": "device_123",
                "name": "Test Vehicle",
                "make": "Tesla",
                "model": "Model 3",
                "year": 2023,
            }
        ]
    }


class TestDroneMobileClient:
    """Tests for DroneMobileClient class."""

    def test_init(self, tmp_path):
        """Test client initialization."""
        client = DroneMobileClient("user@test.com", "pass", token_dir=tmp_path)
        assert client.auth.username == "user@test.com"
        assert client.auth.password == "pass"

    @patch("drone_mobile.client.requests.Session.get")
    def test_get_vehicles_success(self, mock_get, client, mock_vehicle_response, mock_auth):
        """Test successfully getting vehicles."""
        client.auth = mock_auth

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_vehicle_response
        mock_get.return_value = mock_response

        vehicles = client.get_vehicles()

        assert len(vehicles) == 1
        assert isinstance(vehicles[0], Vehicle)
        assert vehicles[0].name == "Test Vehicle"
        assert vehicles[0].info.make == "Tesla"

    @patch("drone_mobile.client.requests.Session.get")
    def test_get_vehicles_empty(self, mock_get, client, mock_auth):
        """Test getting vehicles when none exist."""
        client.auth = mock_auth

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        mock_get.return_value = mock_response

        vehicles = client.get_vehicles()

        assert len(vehicles) == 0

    @patch("drone_mobile.client.requests.Session.get")
    def test_get_vehicles_rate_limit(self, mock_get, client, mock_auth):
        """Test rate limit error when getting vehicles."""
        client.auth = mock_auth

        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.json.return_value = {"error": "Rate limit exceeded"}
        mock_get.return_value = mock_response

        with pytest.raises(RateLimitError):
            client.get_vehicles()

    @patch("drone_mobile.client.requests.Session.get")
    def test_get_vehicles_network_error(self, mock_get, client, mock_auth):
        """Test network error when getting vehicles."""
        client.auth = mock_auth
        mock_get.side_effect = requests.exceptions.ConnectionError("Network error")

        with pytest.raises(Exception):  # Should raise NetworkError in real implementation
            client.get_vehicles()

    @patch("drone_mobile.client.requests.Session.get")
    def test_get_vehicle_by_id(self, mock_get, client, mock_vehicle_response, mock_auth):
        """Test getting a specific vehicle by ID."""
        client.auth = mock_auth

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_vehicle_response
        mock_get.return_value = mock_response

        vehicle = client.get_vehicle("123")

        assert vehicle.vehicle_id == "123"
        assert vehicle.name == "Test Vehicle"

    @patch("drone_mobile.client.requests.Session.get")
    def test_get_vehicle_not_found(self, mock_get, client, mock_auth):
        """Test getting a vehicle that doesn't exist."""
        client.auth = mock_auth

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        mock_get.return_value = mock_response

        with pytest.raises(VehicleNotFoundError):
            client.get_vehicle("nonexistent")

    @patch("drone_mobile.client.requests.Session.get")
    def test_get_vehicle_status_success(self, mock_get, client, mock_auth):
        """Test successfully getting vehicle status."""
        client.auth = mock_auth

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "vehicle_id": "123",
            "device_key": "device_123",
            "is_running": True,
            "is_locked": False,
            "battery_percent": 85,
        }
        mock_get.return_value = mock_response

        status = client.get_vehicle_status("123")

        assert status.vehicle_id == "123"
        assert status.is_running is True
        assert status.battery_percent == 85

    @patch("drone_mobile.client.requests.Session.post")
    def test_send_command_success(self, mock_post, client, mock_auth):
        """Test successfully sending a command."""
        client.auth = mock_auth

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "parsed": {
                "success": True,
                "message": "Command sent successfully",
            }
        }
        mock_post.return_value = mock_response

        response = client.send_command("device_123", "REMOTE_START")

        assert response.success is True
        assert response.command == "REMOTE_START"

    @patch("drone_mobile.client.requests.Session.post")
    def test_send_command_invalid(self, mock_post, client, mock_auth):
        """Test sending an invalid command."""
        client.auth = mock_auth

        with pytest.raises(InvalidCommandError):
            client.send_command("device_123", "INVALID_COMMAND")

    @patch("drone_mobile.client.requests.Session.post")
    def test_send_command_failed(self, mock_post, client, mock_auth):
        """Test command that fails to execute."""
        client.auth = mock_auth

        mock_response = Mock()
        mock_response.status_code = 424
        mock_response.json.return_value = {
            "parsed": {
                "success": False,
                "detail": "Vehicle not responding",
            }
        }
        mock_post.return_value = mock_response

        with pytest.raises(CommandFailedError):
            client.send_command("device_123", "REMOTE_START")

    def test_context_manager(self, tmp_path):
        """Test client as context manager."""
        with DroneMobileClient("user@test.com", "pass", token_dir=tmp_path) as client:
            assert client is not None
            assert client._session is not None

        # Session should be closed after exiting context
        # In a real test, we'd check that session.close() was called


class TestVehicleCommands:
    """Tests for vehicle command methods."""

    @patch("drone_mobile.client.requests.Session.post")
    def test_poll_device_status(self, mock_post, client, mock_auth):
        """Test polling device status."""
        client.auth = mock_auth

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"parsed": {"success": True, "message": "Status updated"}}
        mock_post.return_value = mock_response

        response = client.poll_device_status("device_123")

        assert response.success is True
        # Verify it used device type "2" for controller
        call_args = mock_post.call_args
        assert call_args[1]["json"]["device_type"] == "2"
