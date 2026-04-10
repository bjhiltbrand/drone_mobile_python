"""
DroneMobile Python API Wrapper.

A Python library for interacting with the DroneMobile API to control
Firstech/Compustar remote start systems.
"""

__version__ = "0.3.4"
__author__ = "bjhiltbrand"

from .client import DroneMobileClient
from .exceptions import (
    APIError,
    AuthenticationError,
    CommandFailedError,
    DroneMobileException,
    InvalidCommandError,
    InvalidCredentialsError,
    MFARequiredError,
    NetworkError,
    RateLimitError,
    TokenExpiredError,
    VehicleNotFoundError,
)
from .models import AuthToken, CommandResponse, Location, VehicleInfo, VehicleStatus
from .vehicle import Vehicle

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
    "MFARequiredError",
    "APIError",
    "CommandFailedError",
    "VehicleNotFoundError",
    "InvalidCommandError",
    "RateLimitError",
    "NetworkError",
]
