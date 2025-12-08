"""Data models for DroneMobile entities."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict


@dataclass
class Location:
    """Represents a vehicle's geographic location."""

    latitude: float
    longitude: float
    timestamp: datetime | None = None
    accuracy: float | None = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Location":
        """Create a Location from API response data."""
        return cls(
            latitude=float(data.get("latitude", 0)),
            longitude=float(data.get("longitude", 0)),
            timestamp=datetime.fromisoformat(data["timestamp"]) if "timestamp" in data else None,
            accuracy=float(data["accuracy"]) if "accuracy" in data else None,
        )


@dataclass
class VehicleStatus:
    """Represents the current status of a vehicle."""

    vehicle_id: str
    device_key: str
    is_running: bool = False
    is_locked: bool = False
    battery_voltage: float | None = None
    battery_percent: int | None = None
    odometer: float | None = None
    fuel_level: int | None = None
    interior_temperature: float | None = None
    exterior_temperature: float | None = None
    location: Location | None = None
    last_updated: datetime | None = None
    raw_data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VehicleStatus":
        """Create a VehicleStatus from API response data."""
        # Extract last_known_state if present (from vehicle info endpoint)
        lks = data.get("last_known_state", {})
        controller = lks.get("controller", {})

        # Get location data - could be in different places
        location = None
        if "latitude" in lks and "longitude" in lks:
            location = Location(
                latitude=float(lks["latitude"]),
                longitude=float(lks["longitude"]),
                timestamp=None,
                accuracy=None,
            )
        elif "location" in data:
            location = Location.from_dict(data["location"])

        # Parse timestamp
        last_updated = None
        timestamp_str = lks.get("timestamp") or data.get("last_updated")
        if timestamp_str:
            try:
                last_updated = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass

        return cls(
            vehicle_id=data.get("id", data.get("vehicle_id", "")),
            device_key=data.get("device_key", ""),
            is_running=controller.get("engine_on", False),
            is_locked=controller.get("armed", False),
            battery_voltage=controller.get("main_battery_voltage"),
            battery_percent=None,  # Not provided by API
            odometer=lks.get("mileage"),
            fuel_level=None,  # Not provided by API
            interior_temperature=controller.get("current_temperature"),
            exterior_temperature=None,  # Not provided by API separately
            location=location,
            last_updated=last_updated,
            raw_data=data,
        )


@dataclass
class VehicleInfo:
    """Represents basic information about a vehicle."""

    vehicle_id: str
    device_key: str
    name: str
    make: str | None = None
    model: str | None = None
    year: int | None = None
    color: str | None = None
    vin: str | None = None
    raw_data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VehicleInfo":
        """Create a VehicleInfo from API response data."""
        # The API returns different field names than expected
        # Handle both the standard fields and the vehicle_ prefixed ones
        return cls(
            vehicle_id=data.get("id", data.get("vehicle_id", "")),
            device_key=data.get("device_key", ""),
            name=data.get("vehicle_name", data.get("name", "Unknown Vehicle")),
            make=data.get("vehicle_make", data.get("make")),
            model=data.get("vehicle_model", data.get("model")),
            year=(
                int(data["vehicle_year"])
                if data.get("vehicle_year")
                else (int(data["year"]) if data.get("year") else None)
            ),
            color=data.get("color"),
            vin=data.get("vin"),
            raw_data=data,
        )


@dataclass
class CommandResponse:
    """Represents the response from a vehicle command."""

    success: bool
    message: str
    command: str
    device_key: str
    timestamp: datetime | None = None
    raw_data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any], command: str, device_key: str) -> "CommandResponse":
        """Create a CommandResponse from API response data."""
        timestamp = None
        if "timestamp" in data:
            try:
                timestamp = datetime.fromisoformat(data["timestamp"])
            except (ValueError, TypeError):
                pass

        return cls(
            success=data.get("success", False),
            message=data.get("message", ""),
            command=command,
            device_key=device_key,
            timestamp=timestamp,
            raw_data=data,
        )


@dataclass
class AuthToken:
    """Represents authentication tokens and metadata."""

    access_token: str
    id_token: str
    refresh_token: str
    token_type: str
    expires_at: datetime

    def is_expired(self) -> bool:
        """Check if the access token has expired."""
        return datetime.now() >= self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "access_token": self.access_token,
            "id_token": self.id_token,
            "refresh_token": self.refresh_token,
            "token_type": self.token_type,
            "expires_at": self.expires_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuthToken":
        """Create an AuthToken from stored data."""
        return cls(
            access_token=data["access_token"],
            id_token=data["id_token"],
            refresh_token=data["refresh_token"],
            token_type=data["token_type"],
            expires_at=datetime.fromisoformat(data["expires_at"]),
        )
