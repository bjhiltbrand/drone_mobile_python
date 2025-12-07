"""Vehicle class representing a DroneMobile-connected vehicle."""

import logging
from typing import TYPE_CHECKING

from .models import CommandResponse, VehicleInfo, VehicleStatus

if TYPE_CHECKING:
    from .client import DroneMobileClient

_LOGGER = logging.getLogger(__name__)


class Vehicle:
    """Represents a vehicle with DroneMobile connectivity."""

    def __init__(self, client: "DroneMobileClient", info: VehicleInfo):
        """
        Initialize a Vehicle.

        Args:
            client: The DroneMobileClient instance
            info: VehicleInfo object with vehicle details
        """
        self._client = client
        self.info = info
        self._cached_status: VehicleStatus | None = None

    @property
    def vehicle_id(self) -> str:
        """Get the vehicle's unique identifier."""
        return self.info.vehicle_id

    @property
    def device_key(self) -> str:
        """Get the vehicle's device key."""
        return self.info.device_key

    @property
    def name(self) -> str:
        """Get the vehicle's name."""
        return self.info.name

    def get_status(self, use_cache: bool = False) -> VehicleStatus:
        """
        Get the current status of the vehicle.

        Args:
            use_cache: If True, return cached status without making API call

        Returns:
            VehicleStatus object

        Raises:
            APIError: If API request fails
        """
        if use_cache and self._cached_status:
            return self._cached_status

        self._cached_status = self._client.get_vehicle_status(self.vehicle_id)
        return self._cached_status

    def poll_status(self) -> CommandResponse:
        """
        Poll the vehicle's device for status updates.

        Returns:
            CommandResponse object

        Raises:
            APIError: If API request fails
        """
        _LOGGER.info(f"Polling status for {self.name}")
        return self._client.poll_device_status(self.device_key)

    def start(self) -> CommandResponse:
        """
        Start the vehicle's engine remotely.

        Returns:
            CommandResponse object

        Raises:
            CommandFailedError: If command fails
            APIError: If API request fails
        """
        _LOGGER.info(f"Starting engine for {self.name}")
        return self._client.send_command(self.device_key, "REMOTE_START")

    def stop(self) -> CommandResponse:
        """
        Stop the vehicle's engine remotely.

        Returns:
            CommandResponse object

        Raises:
            CommandFailedError: If command fails
            APIError: If API request fails
        """
        _LOGGER.info(f"Stopping engine for {self.name}")
        return self._client.send_command(self.device_key, "REMOTE_STOP")

    def lock(self) -> CommandResponse:
        """
        Lock the vehicle's doors (arm the security system).

        Returns:
            CommandResponse object

        Raises:
            CommandFailedError: If command fails
            APIError: If API request fails
        """
        _LOGGER.info(f"Locking {self.name}")
        return self._client.send_command(self.device_key, "ARM")

    def unlock(self) -> CommandResponse:
        """
        Unlock the vehicle's doors (disarm the security system).

        Returns:
            CommandResponse object

        Raises:
            CommandFailedError: If command fails
            APIError: If API request fails
        """
        _LOGGER.info(f"Unlocking {self.name}")
        return self._client.send_command(self.device_key, "DISARM")

    def trunk(self) -> CommandResponse:
        """
        Open the vehicle's trunk.

        Returns:
            CommandResponse object

        Raises:
            CommandFailedError: If command fails
            APIError: If API request fails
        """
        _LOGGER.info(f"Opening trunk for {self.name}")
        return self._client.send_command(self.device_key, "TRUNK")

    def panic_on(self) -> CommandResponse:
        """
        Activate the vehicle's panic alarm.

        Returns:
            CommandResponse object

        Raises:
            CommandFailedError: If command fails
            APIError: If API request fails
        """
        _LOGGER.info(f"Activating panic for {self.name}")
        return self._client.send_command(self.device_key, "PANIC_ON")

    def panic_off(self) -> CommandResponse:
        """
        Deactivate the vehicle's panic alarm.

        Returns:
            CommandResponse object

        Raises:
            CommandFailedError: If command fails
            APIError: If API request fails
        """
        _LOGGER.info(f"Deactivating panic for {self.name}")
        return self._client.send_command(self.device_key, "PANIC_OFF")

    def aux1(self) -> CommandResponse:
        """
        Trigger the auxiliary 1 function.

        Returns:
            CommandResponse object

        Raises:
            CommandFailedError: If command fails
            APIError: If API request fails
        """
        _LOGGER.info(f"Triggering AUX1 for {self.name}")
        return self._client.send_command(self.device_key, "REMOTE_AUX1")

    def aux2(self) -> CommandResponse:
        """
        Trigger the auxiliary 2 function.

        Returns:
            CommandResponse object

        Raises:
            CommandFailedError: If command fails
            APIError: If API request fails
        """
        _LOGGER.info(f"Triggering AUX2 for {self.name}")
        return self._client.send_command(self.device_key, "REMOTE_AUX2")

    def get_location(self) -> CommandResponse:
        """
        Request the vehicle's current GPS location.

        Returns:
            CommandResponse object

        Raises:
            CommandFailedError: If command fails
            APIError: If API request fails
        """
        _LOGGER.info(f"Requesting location for {self.name}")
        return self._client.send_command(self.device_key, "LOCATION")

    def __repr__(self) -> str:
        """String representation of the vehicle."""
        return (
            f"Vehicle(id={self.vehicle_id}, name={self.name}, "
            f"make={self.info.make}, model={self.info.model}, year={self.info.year})"
        )

    def __str__(self) -> str:
        """Human-readable string representation."""
        if self.info.make and self.info.model and self.info.year:
            return f"{self.info.year} {self.info.make} {self.info.model} ({self.name})"
        return self.name
