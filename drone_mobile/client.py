"""DroneMobile API client."""

import logging
from pathlib import Path
from types import TracebackType  # Added for robust __exit__ typing
from typing import Dict, List

import requests

from .auth import AuthenticationManager
from .const import (
    API_VERSION,
    AVAILABLE_COMMANDS,
    BASE_API_URL,
    DEFAULT_HEADERS,
    DEFAULT_TIMEOUT,
    DEVICE_TYPE_CONTROLLER,
    DEVICE_TYPE_VEHICLE,
    URLS,
)
from .exceptions import (
    APIError,
    CommandFailedError,
    InvalidCommandError,
    NetworkError,
    RateLimitError,
    VehicleNotFoundError,
)
from .models import CommandResponse, VehicleInfo, VehicleStatus
from .vehicle import Vehicle

_LOGGER = logging.getLogger(__name__)


class DroneMobileClient:
    """Client for interacting with the DroneMobile API."""

    def __init__(
        self,
        username: str,
        password: str,
        token_dir: Path | None = None,
    ):
        """
        Initialize the DroneMobile client.

        Args:
            username: DroneMobile account username/email
            password: DroneMobile account password
            token_dir: Optional directory for token storage
        """
        self.auth = AuthenticationManager(username, password, token_dir)
        self._session = requests.Session()
        self._vehicles: Dict[str, Vehicle] = {}

    def get_vehicles(self) -> List[Vehicle]:  # Corrected redundant type hint
        """
        Get all vehicles associated with the account.

        Returns:
            List of Vehicle objects

        Raises:
            APIError: If API request fails
            NetworkError: If network request fails
        """
        _LOGGER.debug("Fetching all vehicles")

        headers = {**DEFAULT_HEADERS, **self.auth.get_auth_headers()}

        try:
            response = self._session.get(
                URLS["vehicle_info"],
                headers=headers,
                timeout=DEFAULT_TIMEOUT,
            )
        except requests.exceptions.RequestException as e:
            raise NetworkError(f"Network error fetching vehicles: {e}") from e

        if response.status_code == 200:
            results = response.json().get("results", [])
            vehicles = []

            for vehicle_data in results:
                vehicle_info = VehicleInfo.from_dict(vehicle_data)
                vehicle = Vehicle(self, vehicle_info)
                self._vehicles[vehicle_info.vehicle_id] = vehicle
                vehicles.append(vehicle)

            _LOGGER.info(f"Found {len(vehicles)} vehicle(s)")
            return vehicles
        elif response.status_code == 401:
            _LOGGER.debug("Token expired, refreshing and retrying")
            self.auth.authenticate(force_refresh=True)
            return self.get_vehicles()
        elif response.status_code == 429:
            raise RateLimitError(
                "API rate limit exceeded", response.status_code, response.json()
            )  # Removed invalid 'from e'
        else:
            raise APIError(
                f"Failed to fetch vehicles: {response.text}",
                response.status_code,
                response.json() if response.content else None,
            )

    def get_vehicle(self, vehicle_id: str) -> Vehicle:
        """
        Get a specific vehicle by ID.

        Args:
            vehicle_id: The vehicle's unique identifier

        Returns:
            Vehicle object

        Raises:
            VehicleNotFoundError: If vehicle is not found
            APIError: If API request fails
        """
        if vehicle_id in self._vehicles:
            return self._vehicles[vehicle_id]

        # Fetch all vehicles and find the requested one
        vehicles = self.get_vehicles()
        for vehicle in vehicles:
            if vehicle.info.vehicle_id == vehicle_id:
                return vehicle
        raise VehicleNotFoundError(f"Vehicle with ID {vehicle_id} not found")

    def get_vehicle_status(self, vehicle_id: str) -> VehicleStatus:
        """
        Get the current status of a vehicle.

        Args:
            vehicle_id: The vehicle's unique identifier

        Returns:
            VehicleStatus object

        Raises:
            APIError: If API request fails
            NetworkError: If network request fails
        """
        _LOGGER.debug(f"Fetching status for vehicle {vehicle_id}")

        headers = {**DEFAULT_HEADERS, **self.auth.get_auth_headers()}
        url = f"{BASE_API_URL}{API_VERSION}/vehicle/{vehicle_id}"

        try:
            response = self._session.get(
                url,
                headers=headers,
                timeout=DEFAULT_TIMEOUT,
            )
        except requests.exceptions.RequestException as e:
            raise NetworkError(f"Network error fetching vehicle status: {e}") from e

        if response.status_code == 200:
            data = response.json()
            return VehicleStatus.from_dict(data)
        elif response.status_code == 401:
            _LOGGER.debug("Token expired, refreshing and retrying")
            self.auth.authenticate(force_refresh=True)
            return self.get_vehicle_status(vehicle_id)
        elif response.status_code == 404:
            raise VehicleNotFoundError(f"Vehicle {vehicle_id} not found")
        elif response.status_code == 429:
            raise RateLimitError("API rate limit exceeded", response.status_code, response.json())
        else:
            raise APIError(
                f"Failed to fetch vehicle status: {response.text}",
                response.status_code,
                response.json() if response.content else None,
            )

    def send_command(
        self,
        device_key: str,
        command: str,
        device_type: str = DEVICE_TYPE_VEHICLE,
    ) -> CommandResponse:
        """
        Send a command to a vehicle.

        Args:
            device_key: The device key for the vehicle
            command: The command to send (must be in AVAILABLE_COMMANDS)
            device_type: The device type (default: vehicle)

        Returns:
            CommandResponse object

        Raises:
            InvalidCommandError: If command is not valid
            CommandFailedError: If command execution fails
            APIError: If API request fails
            NetworkError: If network request fails
        """
        if command not in AVAILABLE_COMMANDS:
            raise InvalidCommandError(
                f"Invalid command '{command}'. Must be one of: {', '.join(AVAILABLE_COMMANDS)}"
            )

        _LOGGER.debug(f"Sending {command} command to device {device_key}")

        headers = {**DEFAULT_HEADERS, **self.auth.get_auth_headers()}
        payload = {
            "device_key": device_key,
            "command": command,
            "device_type": device_type,
        }

        try:
            response = self._session.post(
                URLS["command"],
                json=payload,
                headers=headers,
                timeout=DEFAULT_TIMEOUT,
            )
        except requests.exceptions.RequestException as e:
            raise NetworkError(f"Network error sending command: {e}") from e

        if response.status_code == 200:
            data = response.json().get("parsed", {})
            return CommandResponse.from_dict(data, command, device_key)
        elif response.status_code == 401:
            _LOGGER.debug("Token expired, refreshing and retrying")
            self.auth.authenticate(force_refresh=True)
            return self.send_command(device_key, command, device_type)
        elif response.status_code == 424:
            error_data = response.json().get("parsed", {})
            detail = error_data.get("detail", "Command failed")
            raise CommandFailedError(
                f"Command {command} failed: {detail}",
                response.status_code,
                error_data,
            )
        elif response.status_code == 429:
            raise RateLimitError("API rate limit exceeded", response.status_code, response.json())
        else:
            raise APIError(
                f"Failed to send command: {response.text}",
                response.status_code,
                response.json() if response.content else None,
            )

    def poll_device_status(self, device_key: str) -> CommandResponse:
        """
        Poll the device for status updates.

        Args:
            device_key: The device key for the vehicle

        Returns:
            CommandResponse object

        Raises:
            APIError: If API request fails
        """
        return self.send_command(device_key, "DEVICE_STATUS", DEVICE_TYPE_CONTROLLER)

    def close(self) -> None:
        """Close the HTTP session."""
        self._session.close()
        _LOGGER.debug("Client session closed")

    def __enter__(self) -> "DroneMobileClient":
        """Context manager entry."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Context manager exit."""
        self.close()
