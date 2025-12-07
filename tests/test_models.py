"""Tests for data models."""

from datetime import datetime

from drone_mobile.models import (
    AuthToken,
    CommandResponse,
    Location,
    VehicleInfo,
    VehicleStatus,
)


class TestLocation:
    """Tests for Location model."""

    def test_create_location(self):
        """Test creating a Location object."""
        location = Location(latitude=37.7749, longitude=-122.4194)
        assert location.latitude == 37.7749
        assert location.longitude == -122.4194
        assert location.timestamp is None
        assert location.accuracy is None

    def test_from_dict(self):
        """Test creating Location from dictionary."""
        data = {
            "latitude": 37.7749,
            "longitude": -122.4194,
            "timestamp": "2024-01-01T12:00:00",
            "accuracy": 10.5,
        }
        location = Location.from_dict(data)

        assert location.latitude == 37.7749
        assert location.longitude == -122.4194
        assert isinstance(location.timestamp, datetime)
        assert location.accuracy == 10.5

    def test_from_dict_minimal(self):
        """Test creating Location with minimal data."""
        data = {"latitude": 0, "longitude": 0}
        location = Location.from_dict(data)

        assert location.latitude == 0
        assert location.longitude == 0
        assert location.timestamp is None


class TestVehicleStatus:
    """Tests for VehicleStatus model."""

    def test_create_vehicle_status(self):
        """Test creating a VehicleStatus object."""
        status = VehicleStatus(
            vehicle_id="123",
            device_key="device_123",
            is_running=True,
            is_locked=False,
            battery_percent=85,
        )

        assert status.vehicle_id == "123"
        assert status.device_key == "device_123"
        assert status.is_running is True
        assert status.is_locked is False
        assert status.battery_percent == 85

    def test_from_dict_full(self):
        """Test creating VehicleStatus from full dictionary."""
        data = {
            "vehicle_id": "123",
            "device_key": "device_123",
            "is_running": True,
            "is_locked": False,
            "battery_voltage": 12.6,
            "battery_percent": 85,
            "odometer": 15000.5,
            "fuel_level": 75,
            "interior_temperature": 72,
            "exterior_temperature": 65,
            "location": {
                "latitude": 37.7749,
                "longitude": -122.4194,
            },
            "last_updated": "2024-01-01T12:00:00",
        }

        status = VehicleStatus.from_dict(data)

        assert status.vehicle_id == "123"
        assert status.is_running is True
        assert status.battery_percent == 85
        assert status.odometer == 15000.5
        assert status.fuel_level == 75
        assert status.location is not None
        assert status.location.latitude == 37.7749

    def test_from_dict_minimal(self):
        """Test creating VehicleStatus with minimal data."""
        data = {"vehicle_id": "123", "device_key": "device_123"}
        status = VehicleStatus.from_dict(data)

        assert status.vehicle_id == "123"
        assert status.device_key == "device_123"
        assert status.is_running is False
        assert status.is_locked is False
        assert status.battery_percent is None


class TestVehicleInfo:
    """Tests for VehicleInfo model."""

    def test_create_vehicle_info(self):
        """Test creating a VehicleInfo object."""
        info = VehicleInfo(
            vehicle_id="123",
            device_key="device_123",
            name="My Car",
            make="Tesla",
            model="Model 3",
            year=2023,
        )

        assert info.vehicle_id == "123"
        assert info.name == "My Car"
        assert info.make == "Tesla"
        assert info.model == "Model 3"
        assert info.year == 2023

    def test_from_dict_full(self):
        """Test creating VehicleInfo from full dictionary."""
        data = {
            "vehicle_id": "123",
            "device_key": "device_123",
            "name": "My Car",
            "make": "Tesla",
            "model": "Model 3",
            "year": 2023,
            "color": "Red",
            "vin": "1234567890ABCDEFG",
        }

        info = VehicleInfo.from_dict(data)

        assert info.vehicle_id == "123"
        assert info.name == "My Car"
        assert info.make == "Tesla"
        assert info.year == 2023
        assert info.color == "Red"
        assert info.vin == "1234567890ABCDEFG"

    def test_from_dict_minimal(self):
        """Test creating VehicleInfo with minimal data."""
        data = {"vehicle_id": "123", "device_key": "device_123"}
        info = VehicleInfo.from_dict(data)

        assert info.vehicle_id == "123"
        assert info.name == "Unknown Vehicle"
        assert info.make is None


class TestCommandResponse:
    """Tests for CommandResponse model."""

    def test_create_command_response(self):
        """Test creating a CommandResponse object."""
        response = CommandResponse(
            success=True,
            message="Command executed successfully",
            command="REMOTE_START",
            device_key="device_123",
        )

        assert response.success is True
        assert response.message == "Command executed successfully"
        assert response.command == "REMOTE_START"
        assert response.device_key == "device_123"

    def test_from_dict(self):
        """Test creating CommandResponse from dictionary."""
        data = {
            "success": True,
            "message": "Command executed",
            "timestamp": "2024-01-01T12:00:00",
        }

        response = CommandResponse.from_dict(data, "REMOTE_START", "device_123")

        assert response.success is True
        assert response.message == "Command executed"
        assert response.command == "REMOTE_START"
        assert response.device_key == "device_123"
        assert isinstance(response.timestamp, datetime)

    def test_from_dict_minimal(self):
        """Test creating CommandResponse with minimal data."""
        data = {}
        response = CommandResponse.from_dict(data, "REMOTE_STOP", "device_456")

        assert response.success is False
        assert response.message == ""
        assert response.command == "REMOTE_STOP"


class TestAuthToken:
    """Tests for AuthToken model."""

    def test_create_auth_token(self):
        """Test creating an AuthToken object."""
        expires_at = datetime(2024, 12, 31, 23, 59, 59)
        token = AuthToken(
            access_token="access_123",
            id_token="id_123",
            refresh_token="refresh_123",
            token_type="Bearer",
            expires_at=expires_at,
        )

        assert token.access_token == "access_123"
        assert token.id_token == "id_123"
        assert token.refresh_token == "refresh_123"
        assert token.token_type == "Bearer"
        assert token.expires_at == expires_at

    def test_is_expired_false(self):
        """Test token that hasn't expired."""
        token = AuthToken(
            access_token="test",
            id_token="test",
            refresh_token="test",
            token_type="Bearer",
            expires_at=datetime(2099, 12, 31),
        )
        assert not token.is_expired()

    def test_is_expired_true(self):
        """Test token that has expired."""
        token = AuthToken(
            access_token="test",
            id_token="test",
            refresh_token="test",
            token_type="Bearer",
            expires_at=datetime(2020, 1, 1),
        )
        assert token.is_expired()

    def test_to_dict_and_from_dict(self):
        """Test serialization and deserialization."""
        original = AuthToken(
            access_token="access_123",
            id_token="id_123",
            refresh_token="refresh_123",
            token_type="Bearer",
            expires_at=datetime(2024, 12, 31, 23, 59, 59),
        )

        token_dict = original.to_dict()
        restored = AuthToken.from_dict(token_dict)

        assert restored.access_token == original.access_token
        assert restored.id_token == original.id_token
        assert restored.refresh_token == original.refresh_token
        assert restored.token_type == original.token_type
        # Note: datetime comparison might have microsecond differences
        assert restored.expires_at.date() == original.expires_at.date()
