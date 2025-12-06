"""Async client for DroneMobile API (requires aiohttp)."""

import asyncio
import logging
from pathlib import Path
from types import TracebackType
from typing import Dict, List, Optional

try:
    import aiohttp
except ImportError as e:
    raise ImportError(
        "aiohttp is required for async support. " "Install with: pip install drone_mobile[async]"
    ) from e

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

_LOGGER = logging.getLogger(__name__)


class AsyncVehicle:
    """Async version of Vehicle class."""

    def __init__(self, client: "AsyncDroneMobileClient", info: VehicleInfo):
        """Initialize an async vehicle."""
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

    async def get_status(self, use_cache: bool = False) -> VehicleStatus:
        """Get the current status of the vehicle."""
        if use_cache and self._cached_status:
            return self._cached_status

        self._cached_status = await self._client.get_vehicle_status(self.vehicle_id)
        return self._cached_status

    async def poll_status(self) -> CommandResponse:
        """Poll the vehicle's device for status updates."""
        _LOGGER.info(f"Polling status for {self.name}")
        return await self._client.poll_device_status(self.device_key)

    async def start(self) -> CommandResponse:
        """Start the vehicle's engine remotely."""
        _LOGGER.info(f"Starting engine for {self.name}")
        return await self._client.send_command(self.device_key, "REMOTE_START")

    async def stop(self) -> CommandResponse:
        """Stop the vehicle's engine remotely."""
        _LOGGER.info(f"Stopping engine for {self.name}")
        return await self._client.send_command(self.device_key, "REMOTE_STOP")

    async def lock(self) -> CommandResponse:
        """Lock the vehicle's doors."""
        _LOGGER.info(f"Locking {self.name}")
        return await self._client.send_command(self.device_key, "ARM")

    async def unlock(self) -> CommandResponse:
        """Unlock the vehicle's doors."""
        _LOGGER.info(f"Unlocking {self.name}")
        return await self._client.send_command(self.device_key, "DISARM")

    async def trunk(self) -> CommandResponse:
        """Open the vehicle's trunk."""
        _LOGGER.info(f"Opening trunk for {self.name}")
        return await self._client.send_command(self.device_key, "TRUNK")

    async def panic_on(self) -> CommandResponse:
        """Activate the vehicle's panic alarm."""
        _LOGGER.info(f"Activating panic for {self.name}")
        return await self._client.send_command(self.device_key, "PANIC_ON")

    async def panic_off(self) -> CommandResponse:
        """Deactivate the vehicle's panic alarm."""
        _LOGGER.info(f"Deactivating panic for {self.name}")
        return await self._client.send_command(self.device_key, "PANIC_OFF")

    async def aux1(self) -> CommandResponse:
        """Trigger the auxiliary 1 function."""
        _LOGGER.info(f"Triggering AUX1 for {self.name}")
        return await self._client.send_command(self.device_key, "REMOTE_AUX1")

    async def aux2(self) -> CommandResponse:
        """Trigger the auxiliary 2 function."""
        _LOGGER.info(f"Triggering AUX2 for {self.name}")
        return await self._client.send_command(self.device_key, "REMOTE_AUX2")

    async def get_location(self) -> CommandResponse:
        """Request the vehicle's current GPS location."""
        _LOGGER.info(f"Requesting location for {self.name}")
        return await self._client.send_command(self.device_key, "LOCATION")

    def __repr__(self) -> str:
        """String representation of the vehicle."""
        return (
            f"AsyncVehicle(id={self.vehicle_id}, name={self.name}, "
            f"make={self.info.make}, model={self.info.model}, year={self.info.year})"
        )


class AsyncDroneMobileClient:
    """Async client for interacting with the DroneMobile API."""

    def __init__(
        self,
        username: str,
        password: str,
        token_dir: Path | None = None,
    ):
        """
        Initialize the async DroneMobile client.

        Args:
            username: DroneMobile account username/email
            password: DroneMobile account password
            token_dir: Optional directory for token storage
        """
        self.auth = AuthenticationManager(username, password, token_dir)
        self._session: Optional[aiohttp.ClientSession] = None
        self._vehicles: Dict[str, AsyncVehicle] = {}

    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Ensure an active session exists."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def get_vehicles(self) -> List[AsyncVehicle]:
        """
        Get all vehicles associated with the account.

        Returns:
            List of AsyncVehicle objects
        """
        _LOGGER.debug("Fetching all vehicles")
        session = await self._ensure_session()
        headers = {**DEFAULT_HEADERS, **self.auth.get_auth_headers()}

        try:
            async with session.get(URLS["vehicle_info"], headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    results = data.get("results", [])
                    vehicles = []

                    for vehicle_data in results:
                        vehicle_info = VehicleInfo.from_dict(vehicle_data)
                        vehicle = AsyncVehicle(self, vehicle_info)
                        self._vehicles[vehicle_info.vehicle_id] = vehicle
                        vehicles.append(vehicle)

                    _LOGGER.info(f"Found {len(vehicles)} vehicle(s)")
                    return vehicles
                elif response.status == 401:
                    _LOGGER.debug("Token expired, refreshing and retrying")
                    self.auth.authenticate(force_refresh=True)
                    return await self.get_vehicles()
                elif response.status == 429:
                    raise RateLimitError(
                        "API rate limit exceeded", response.status, await response.json()
                    )
                else:
                    text = await response.text()
                    raise APIError(
                        f"Failed to fetch vehicles: {text}",
                        response.status,
                        await response.json() if response.content_length else None,
                    )
        except aiohttp.ClientError as e:
            raise NetworkError(f"Network error fetching vehicles: {e}") from e

    async def get_vehicle(self, vehicle_id: str) -> AsyncVehicle:
        """Get a specific vehicle by ID."""
        if vehicle_id in self._vehicles:
            return self._vehicles[vehicle_id]

        vehicles = await self.get_vehicles()
        for vehicle in vehicles:
            if vehicle.info.vehicle_id == vehicle_id:
                return vehicle

        raise VehicleNotFoundError(f"Vehicle with ID {vehicle_id} not found")

    async def get_vehicle_status(self, vehicle_id: str) -> VehicleStatus:
        """Get the current status of a vehicle."""
        _LOGGER.debug(f"Fetching status for vehicle {vehicle_id}")
        session = await self._ensure_session()
        headers = {**DEFAULT_HEADERS, **self.auth.get_auth_headers()}
        url = f"{BASE_API_URL}{API_VERSION}/vehicle/{vehicle_id}"

        try:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    return VehicleStatus.from_dict(data)
                elif response.status == 401:
                    _LOGGER.debug("Token expired, refreshing and retrying")
                    self.auth.authenticate(force_refresh=True)
                    return await self.get_vehicle_status(vehicle_id)
                elif response.status == 404:
                    raise VehicleNotFoundError(f"Vehicle {vehicle_id} not found")
                elif response.status == 429:
                    raise RateLimitError(
                        "API rate limit exceeded", response.status, await response.json()
                    )
                else:
                    text = await response.text()
                    raise APIError(
                        f"Failed to fetch vehicle status: {text}",
                        response.status,
                        await response.json() if response.content_length else None,
                    )
        except aiohttp.ClientError as e:
            raise NetworkError(f"Network error fetching vehicle status: {e}") from e

    async def send_command(
        self,
        device_key: str,
        command: str,
        device_type: str = DEVICE_TYPE_VEHICLE,
    ) -> CommandResponse:
        """Send a command to a vehicle."""
        if command not in AVAILABLE_COMMANDS:
            raise InvalidCommandError(
                f"Invalid command '{command}'. Must be one of: {', '.join(AVAILABLE_COMMANDS)}"
            )

        _LOGGER.debug(f"Sending {command} command to device {device_key}")
        session = await self._ensure_session()
        headers = {**DEFAULT_HEADERS, **self.auth.get_auth_headers()}
        payload = {
            "device_key": device_key,
            "command": command,
            "device_type": device_type,
        }

        try:
            async with session.post(URLS["command"], json=payload, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    parsed = data.get("parsed", {})
                    return CommandResponse.from_dict(parsed, command, device_key)
                elif response.status == 401:
                    _LOGGER.debug("Token expired, refreshing and retrying")
                    self.auth.authenticate(force_refresh=True)
                    return await self.send_command(device_key, command, device_type)
                elif response.status == 424:
                    data = await response.json()
                    error_data = data.get("parsed", {})
                    detail = error_data.get("detail", "Command failed")
                    raise CommandFailedError(
                        f"Command {command} failed: {detail}",
                        response.status,
                        error_data,
                    )
                elif response.status == 429:
                    raise RateLimitError(
                        "API rate limit exceeded", response.status, await response.json()
                    )
                else:
                    text = await response.text()
                    raise APIError(
                        f"Failed to send command: {text}",
                        response.status,
                        await response.json() if response.content_length else None,
                    )
        except aiohttp.ClientError as e:
            raise NetworkError(f"Network error sending command: {e}") from e

    async def poll_device_status(self, device_key: str) -> CommandResponse:
        """Poll the device for status updates."""
        return await self.send_command(device_key, "DEVICE_STATUS", DEVICE_TYPE_CONTROLLER)

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            _LOGGER.debug("Client session closed")

    async def __aenter__(self) -> "AsyncDroneMobileClient":
        """Async context manager entry."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Async context manager exit."""
        await self.close()


# Example usage
async def example() -> None:
    """Example of using the async client."""
    async with AsyncDroneMobileClient("user@example.com", "password") as client:
        vehicles = await client.get_vehicles()

        for vehicle in vehicles:
            print(f"Vehicle: {vehicle.name}")
            status = await vehicle.get_status()
            print(f"  Running: {status.is_running}")
            print(f"  Locked: {status.is_locked}")

        # Start first vehicle
        if vehicles:
            response = await vehicles[0].start()
            print(f"Start command: {response.message}")


if __name__ == "__main__":
    asyncio.run(example())
