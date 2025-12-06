"""
DroneMobile Python API Wrapper.

A Python library for interacting with the DroneMobile API to control
Firstech/Compustar remote start systems.
"""

__version__ = "0.3.0"
__author__ = "bjhiltbrand"

from .client import DroneMobileClient
from .exceptions import (
    APIError,
    AuthenticationError,
    CommandFailedError,
    DroneMobileException,
    InvalidCommandError,
    InvalidCredentialsError,
    NetworkError,
    RateLimitError,
    TokenExpiredError,
    VehicleNotFoundError,
)
from .models import AuthToken, CommandResponse, Location, VehicleInfo, VehicleStatus
from .vehicle import Vehicle

# Backwards compatibility - maintain old import pattern
# This allows: from drone_mobile import Vehicle
# which will actually give them the client
__all__ = [
    # Main classes
    "DroneMobileClient",
    "Vehicle",
    # Models
    "VehicleInfo",
    "VehicleStatus",
    "Location",
    "CommandResponse",
    "AuthToken",
    # Exceptions
    "DroneMobileException",
    "AuthenticationError",
    "TokenExpiredError",
    "InvalidCredentialsError",
    "APIError",
    "CommandFailedError",
    "VehicleNotFoundError",
    "InvalidCommandError",
    "RateLimitError",
    "NetworkError",
]
