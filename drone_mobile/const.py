"""Constants for the DroneMobile python library."""

import os
from pathlib import Path
from typing import Final

# AWS Configuration
AWS_CLIENT_ID: Final[str] = os.getenv("DRONEMOBILE_AWS_CLIENT_ID", "3l3gtebtua7qft45b4splbeuiu")

# API Configuration
BASE_API_URL: Final[str] = "https://api.dronemobile.com/api/"
HOST: Final[str] = "api.dronemobile.com"
API_VERSION: Final[str] = "v1"

# Token expiry safety margin (seconds before actual expiry to refresh)
TOKEN_EXPIRY_MARGIN: Final[int] = 100

# Default timeout for API requests (seconds)
DEFAULT_TIMEOUT: Final[int] = 30

# API Endpoints
URLS: Final[dict] = {
    "auth": "https://cognito-idp.us-east-1.amazonaws.com/",
    "user_info": f"{BASE_API_URL}{API_VERSION}/user",
    "vehicle_info": f"{BASE_API_URL}{API_VERSION}/vehicle?limit=100",
    "command": f"{BASE_API_URL}{API_VERSION}/iot/command",
}

# Available Commands
AVAILABLE_COMMANDS: Final[set] = {
    "DEVICE_STATUS",
    "REMOTE_START",
    "REMOTE_STOP",
    "ARM",
    "DISARM",
    "TRUNK",
    "PANIC_ON",
    "PANIC_OFF",
    "REMOTE_AUX1",
    "REMOTE_AUX2",
    "LOCATION",
}

# Device Types
DEVICE_TYPE_VEHICLE: Final[str] = "1"  # I think this is in reference to the vehicle
DEVICE_TYPE_CONTROLLER: Final[str] = (
    "2"  # I think this is in reference to the DroneMobile Contoller Module
)

AVAILABLE_DEVICE_TYPES: Final[set] = {
    DEVICE_TYPE_VEHICLE,  # Vehicle
    DEVICE_TYPE_CONTROLLER,  # DroneMobile Controller Module
}

# HTTP Headers
COMMAND_HEADERS: Final[dict] = {
    "Authorization": None,
    "Content-Type": "application/json",
}

AUTH_HEADERS: Final[dict] = {
    "Referer": "https://accounts.dronemobile.com/",
    "X-Amz-Target": "AWSCognitoIdentityProviderService.InitiateAuth",
    "X-Amz-User-Agent": "aws-amplify/5.0.4 js",
    "Content-Type": "application/x-amz-json-1.1",
}

# Used for the RespondToAuthChallenge call (MFA step).
# Identical to AUTH_HEADERS except for the Amz-Target.
MFA_CHALLENGE_HEADERS: Final[dict] = {
    "Referer": "https://accounts.dronemobile.com/",
    "X-Amz-Target": "AWSCognitoIdentityProviderService.RespondToAuthChallenge",
    "X-Amz-User-Agent": "aws-amplify/5.0.4 js",
    "Content-Type": "application/x-amz-json-1.1",
}

DEFAULT_HEADERS: Final[dict] = {
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate, br",
}

# Cognito MFA challenge names that this library handles.
# SMS_MFA  – one-time code sent via SMS.
# SOFTWARE_TOKEN_MFA – TOTP code from an authenticator app (e.g. Google Authenticator).
SUPPORTED_MFA_CHALLENGES: Final[frozenset] = frozenset({"SMS_MFA", "SOFTWARE_TOKEN_MFA"})

# Expected length of a valid MFA OTP code.
MFA_CODE_LENGTH: Final[int] = 6

# Token Storage
# Use XDG_CONFIG_HOME if available, otherwise fall back to ~/.config
_config_dir = Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config"))
DEFAULT_TOKEN_DIR: Final[Path] = _config_dir / "drone_mobile"
DEFAULT_TOKEN_FILE: Final[str] = "token.json"

# Legacy token file location for migration
LEGACY_TOKEN_LOCATION: Final[str] = "./drone_mobile_token.txt"
