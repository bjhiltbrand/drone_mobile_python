"""Authentication handler for DroneMobile API."""

import json
import logging
import os
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Optional

import filelock
import requests

from .const import (
    AUTH_HEADERS,
    AWS_CLIENT_ID,
    DEFAULT_HEADERS,
    DEFAULT_TIMEOUT,
    DEFAULT_TOKEN_DIR,
    DEFAULT_TOKEN_FILE,
    LEGACY_TOKEN_LOCATION,
    MFA_CHALLENGE_HEADERS,
    MFA_CODE_LENGTH,
    SUPPORTED_MFA_CHALLENGES,
    TOKEN_EXPIRY_MARGIN,
    URLS,
)
from .device_srp import DeviceSRP, cognito_timestamp, generate_device_verifier
from .exceptions import (
    AuthenticationError,
    InvalidCredentialsError,
    MFARequiredError,
    NetworkError,
    TokenExpiredError,
)
from .models import AuthToken

_LOGGER = logging.getLogger(__name__)

# Type alias: receives the Cognito challenge name (e.g. "SMS_MFA") and
# returns the one-time code string entered by the user.
MFACallback = Callable[[str], str]


class AuthenticationManager:
    """Manages authentication tokens for DroneMobile API.

    MFA / 2-factor authentication
    ------------------------------
    When the DroneMobile Cognito user pool has MFA enabled, ``InitiateAuth``
    returns a ``ChallengeName`` (``SMS_MFA`` or ``SOFTWARE_TOKEN_MFA``) rather
    than the usual ``AuthenticationResult``.  This class resolves the challenge
    automatically, provided you supply an ``mfa_callback``.

    The callback receives the Cognito challenge name as a ``str`` and must
    return the OTP code (also a ``str``).  For interactive CLIs a simple
    ``input()`` wrapper is sufficient::

        def prompt_mfa(challenge_name: str) -> str:
            label = "SMS code" if challenge_name == "SMS_MFA" else "Authenticator code"
            return input(f"{label}: ").strip()

        auth = AuthenticationManager(user, password, mfa_callback=prompt_mfa)

    If MFA is triggered but no callback is supplied, ``MFARequiredError`` is
    raised so callers can handle it at a higher level.
    """

    def __init__(
        self,
        username: str,
        password: str,
        token_dir: Path | None = None,
        token_file: str = DEFAULT_TOKEN_FILE,
        mfa_callback: Optional[MFACallback] = None,
    ):
        """
        Initialize the authentication manager.

        Args:
            username: DroneMobile account username/email
            password: DroneMobile account password
            token_dir: Directory to store token file (default: ~/.config/drone_mobile)
            token_file: Token filename (default: token.json)
            mfa_callback: Optional callable ``(challenge_name: str) -> str`` that
                returns the OTP code when Cognito requires a second factor.
                If ``None`` and MFA is required, ``MFARequiredError`` is raised.
        """
        self.username = username
        self.password = password
        self.token_dir = token_dir or DEFAULT_TOKEN_DIR
        self.token_file = self.token_dir / token_file
        self.device_file = self.token_dir / "device.json"
        self.mfa_callback = mfa_callback
        self._token: AuthToken | None = None
        self._device: dict | None = None
        self._lock = threading.Lock()

        # Set secure permissions on token directory.
        # Moved here from const.py so directory creation only happens when an
        # AuthenticationManager is actually instantiated, not at import time.
        try:
            self.token_dir.mkdir(parents=True, exist_ok=True)
            os.chmod(self.token_dir, 0o700)
        except OSError as e:
            _LOGGER.warning(f"Could not set secure permissions on token directory: {e}")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def authenticate(self, force_refresh: bool = False) -> AuthToken:
        """
        Authenticate and get a valid access token.

        Args:
            force_refresh: Force a new authentication even if token exists

        Returns:
            AuthToken object containing authentication tokens

        Raises:
            AuthenticationError: If authentication fails
            InvalidCredentialsError: If credentials are invalid
            MFARequiredError: If MFA is required and no mfa_callback is set
            NetworkError: If network request fails
        """
        with self._lock:
            if not force_refresh and self._token and not self._token.is_expired():
                return self._token

            # Try to load existing token
            if not force_refresh:
                try:
                    self._token = self._load_token()
                    if self._token and not self._token.is_expired():
                        _LOGGER.debug("Loaded valid token from storage")
                        return self._token
                    elif self._token:
                        _LOGGER.debug("Token expired, refreshing")
                        return self._refresh_token()
                except Exception as e:
                    _LOGGER.debug(f"Could not load token: {e}")

            # Perform new authentication
            return self._authenticate_new()

    def get_auth_headers(self) -> dict:
        """
        Get headers for authenticated API requests.

        Returns:
            Dictionary of headers including authorization

        Raises:
            AuthenticationError: If unable to get valid token
        """
        token = self.authenticate()
        return {
            "Authorization": f"{token.token_type} {token.id_token}",
            "Content-Type": "application/json",
        }

    def invalidate_token(self) -> None:
        """Invalidate the current token and remove from storage."""
        with self._lock:
            self._token = None
            if self.token_file.exists():
                self.token_file.unlink()
                _LOGGER.info("Token invalidated and removed")

    # ------------------------------------------------------------------
    # Private helpers – authentication flow
    # ------------------------------------------------------------------

    def _authenticate_new(self) -> AuthToken:
        """
        Perform new authentication with username and password.

        If Cognito returns an MFA challenge the flow continues in
        ``_respond_to_mfa_challenge``.

        Returns:
            AuthToken object

        Raises:
            InvalidCredentialsError: If credentials are invalid
            AuthenticationError: If authentication fails
            MFARequiredError: If MFA is required and no callback is configured
            NetworkError: If network request fails
        """
        _LOGGER.debug("Performing new authentication")

        auth_params = {"USERNAME": self.username, "PASSWORD": self.password}

        # If this device has been confirmed and remembered, pass its key so
        # Cognito issues a DEVICE_SRP_AUTH challenge (which we can answer
        # unattended) instead of forcing a second factor.
        device = self._load_device()
        if device and device.get("DeviceKey"):
            auth_params["DEVICE_KEY"] = device["DeviceKey"]

        payload = {
            "AuthFlow": "USER_PASSWORD_AUTH",
            "ClientId": AWS_CLIENT_ID,
            "AuthParameters": auth_params,
            "ClientMetadata": {},
        }

        headers = {**DEFAULT_HEADERS, **AUTH_HEADERS}

        try:
            response = requests.post(
                URLS["auth"],
                json=payload,
                headers=headers,
                timeout=DEFAULT_TIMEOUT,
            )
        except requests.exceptions.RequestException as e:
            raise NetworkError(f"Network error during authentication: {e}") from e

        if response.status_code == 200:
            result = response.json()

            # Cognito may return a challenge instead of tokens.
            challenge_name = result.get("ChallengeName")
            if challenge_name == "DEVICE_SRP_AUTH":
                # Remembered device: authenticate via device SRP, no MFA needed.
                return self._respond_to_device_srp(result)
            if challenge_name:
                return self._respond_to_mfa_challenge(result)

            self._token = self._parse_auth_response(result)
            self._save_token(self._token)
            _LOGGER.info("Successfully authenticated")
            return self._token

        elif response.status_code == 400:
            error_data = response.json()
            error_type = error_data.get("__type", "")
            if "NotAuthorizedException" in error_type:
                raise InvalidCredentialsError("Invalid username or password")
            raise AuthenticationError(
                f"Authentication failed: {error_data.get('message', 'Unknown error')}"
            )
        else:
            raise AuthenticationError(
                f"Authentication failed with status {response.status_code}: {response.text}"
            )

    def _respond_to_mfa_challenge(self, challenge_response: dict) -> AuthToken:  # noqa: C901
        """
        Complete an MFA challenge returned by Cognito's ``InitiateAuth``.

        Cognito sends back:
          - ``ChallengeName``: e.g. ``"SMS_MFA"`` or ``"SOFTWARE_TOKEN_MFA"``
          - ``Session``: opaque session token that must be echoed back
          - ``ChallengeParameters``: metadata (e.g. masked phone number for SMS)

        We call ``mfa_callback`` to obtain the OTP, then post it to
        ``RespondToAuthChallenge``.

        Args:
            challenge_response: The raw JSON dict returned by ``InitiateAuth``

        Returns:
            AuthToken object

        Raises:
            MFARequiredError: If no mfa_callback is configured
            AuthenticationError: If the challenge response is rejected
            NetworkError: If the HTTP request fails
        """
        challenge_name: str = challenge_response["ChallengeName"]
        session: str = challenge_response.get("Session", "")
        params: dict = challenge_response.get("ChallengeParameters", {})

        if challenge_name not in SUPPORTED_MFA_CHALLENGES:
            raise AuthenticationError(
                f"Unsupported Cognito challenge: '{challenge_name}'. "
                f"Supported challenges: {sorted(SUPPORTED_MFA_CHALLENGES)}"
            )

        # Guard against a missing or empty Session token before doing anything
        # further — echoing an empty session back to Cognito would produce a
        # confusing error rather than a clear failure message.
        if not session:
            raise AuthenticationError(
                "Cognito challenge response is missing a Session token. "
                "This is unexpected and may indicate an API change."
            )

        if self.mfa_callback is None:
            raise MFARequiredError(challenge_name)

        # Give callers useful context — e.g. the masked destination for SMS.
        _LOGGER.debug(f"MFA challenge received: {challenge_name}, params={params}")
        if challenge_name == "SMS_MFA" and "CODE_DELIVERY_DESTINATION" in params:
            _LOGGER.info("A verification code was sent to %s", params["CODE_DELIVERY_DESTINATION"])

        otp_code = self.mfa_callback(challenge_name)

        if not otp_code or not otp_code.strip():
            raise AuthenticationError("MFA callback returned an empty code.")

        # Validate that the code is exactly MFA_CODE_LENGTH digits before
        # sending it to Cognito, so the user gets a clear local error instead
        # of a cryptic API rejection.
        cleaned_code = otp_code.strip()
        if not cleaned_code.isdigit() or len(cleaned_code) != MFA_CODE_LENGTH:
            raise AuthenticationError(
                f"MFA code must be exactly {MFA_CODE_LENGTH} digits, " f"got: '{cleaned_code}'"
            )

        # Map challenge name to the correct ChallengeResponse key.
        code_key = "SMS_MFA_CODE" if challenge_name == "SMS_MFA" else "SOFTWARE_TOKEN_MFA_CODE"

        # Cognito requires the user pool's *internal* username here (the
        # ``USER_ID_FOR_SRP`` it handed back, i.e. the sub), not the email alias.
        # Echoing the email still yields tokens, but those tokens then cannot
        # call ConfirmDevice ("Invalid device key given"), which silently breaks
        # device remembering. Falling back to self.username keeps SMS-only pools
        # that omit the parameter working.
        srp_username = params.get("USER_ID_FOR_SRP") or self.username

        payload = {
            "ChallengeName": challenge_name,
            "ClientId": AWS_CLIENT_ID,
            "Session": session,
            "ChallengeResponses": {
                "USERNAME": srp_username,
                code_key: cleaned_code,
            },
        }

        headers = {**DEFAULT_HEADERS, **MFA_CHALLENGE_HEADERS}

        try:
            response = requests.post(
                URLS["auth"],
                json=payload,
                headers=headers,
                timeout=DEFAULT_TIMEOUT,
            )
        except requests.exceptions.RequestException as e:
            raise NetworkError(f"Network error during MFA challenge response: {e}") from e

        if response.status_code == 200:
            result = response.json()

            # Guard against nested challenges (e.g. MFA_SETUP) – unlikely but
            # possible in highly customised user pools.
            if "ChallengeName" in result:
                raise AuthenticationError(
                    f"Unexpected nested challenge after MFA: {result['ChallengeName']}"
                )

            self._token = self._parse_auth_response(result)
            self._save_token(self._token)
            _LOGGER.info("MFA challenge resolved – authentication successful")
            return self._token

        elif response.status_code == 400:
            error_data = response.json()
            error_type = error_data.get("__type", "")
            if "CodeMismatchException" in error_type:
                raise AuthenticationError("Incorrect MFA code. Please try again.")
            if "ExpiredCodeException" in error_type:
                raise AuthenticationError("MFA code has expired. Please request a new one.")
            raise AuthenticationError(
                f"MFA challenge failed: {error_data.get('message', 'Unknown error')}"
            )
        else:
            raise AuthenticationError(
                f"MFA challenge failed with status {response.status_code}: {response.text}"
            )

    def _respond_to_device_srp(self, challenge: dict) -> AuthToken:
        """Authenticate a remembered device via Cognito's device SRP exchange.

        When a device has been confirmed and remembered, Cognito issues a
        ``DEVICE_SRP_AUTH`` challenge instead of an MFA challenge. We answer it
        with the stored device password (a two-step SRP handshake:
        ``DEVICE_SRP_AUTH`` -> ``DEVICE_PASSWORD_VERIFIER``), which lets the
        integration re-authenticate without a second factor after the refresh
        token expires.

        Raises:
            AuthenticationError: If no device secret is stored or the handshake
                is rejected (the stale device is cleared so the next attempt
                falls back to a clean login).
            NetworkError: If an HTTP request fails.
        """
        device = self._load_device()
        if not device or not device.get("DevicePassword"):
            raise AuthenticationError(
                "Cognito requested DEVICE_SRP_AUTH but no remembered device "
                "secret is stored; a fresh login is required."
            )

        device_key = device["DeviceKey"]
        username = challenge.get("ChallengeParameters", {}).get("USERNAME") or self.username
        srp = DeviceSRP(device["DeviceGroupKey"], device_key, device["DevicePassword"])

        try:
            # Step 1: send the client SRP public value (SRP_A).
            srp_payload = {
                "ChallengeName": "DEVICE_SRP_AUTH",
                "ClientId": AWS_CLIENT_ID,
                "ChallengeResponses": {
                    "USERNAME": username,
                    "DEVICE_KEY": device_key,
                    "SRP_A": srp.srp_a,
                },
            }
            if challenge.get("Session"):
                srp_payload["Session"] = challenge["Session"]
            verifier = self._cognito_request("RespondToAuthChallenge", srp_payload)

            if verifier.get("ChallengeName") != "DEVICE_PASSWORD_VERIFIER":
                raise AuthenticationError(
                    "Unexpected challenge after DEVICE_SRP_AUTH: "
                    f"{verifier.get('ChallengeName')}"
                )

            # Step 2: prove possession of the device password.
            cp = verifier["ChallengeParameters"]
            timestamp = cognito_timestamp()
            signature = srp.process_challenge(
                cp["SRP_B"], cp["SALT"], cp["SECRET_BLOCK"], timestamp
            )
            verify_payload = {
                "ChallengeName": "DEVICE_PASSWORD_VERIFIER",
                "ClientId": AWS_CLIENT_ID,
                "ChallengeResponses": {
                    "USERNAME": username,
                    "DEVICE_KEY": device_key,
                    "TIMESTAMP": timestamp,
                    "PASSWORD_CLAIM_SECRET_BLOCK": cp["SECRET_BLOCK"],
                    "PASSWORD_CLAIM_SIGNATURE": signature,
                },
            }
            if verifier.get("Session"):
                verify_payload["Session"] = verifier["Session"]
            result = self._cognito_request("RespondToAuthChallenge", verify_payload)
        except AuthenticationError:
            # The remembered device is no longer usable (revoked, rotated, or a
            # bad secret). Drop it so the next attempt does a clean MFA login.
            _LOGGER.warning(
                "Device SRP login failed; clearing remembered device so the next "
                "login starts fresh."
            )
            self._clear_device()
            raise

        self._token = self._parse_auth_response(result)
        self._save_token(self._token)
        _LOGGER.info("Authenticated via remembered device (MFA skipped)")
        return self._token

    def _refresh_token(self) -> AuthToken:
        """
        Refresh an expired access token using the refresh token.

        Returns:
            AuthToken object

        Raises:
            TokenExpiredError: If refresh token is invalid
            AuthenticationError: If refresh fails
            NetworkError: If network request fails
        """
        if not self._token or not self._token.refresh_token:
            raise TokenExpiredError("No refresh token available")

        _LOGGER.debug("Refreshing access token")

        auth_params = {"REFRESH_TOKEN": self._token.refresh_token}
        device = self._load_device()
        if device and device.get("DeviceKey"):
            auth_params["DEVICE_KEY"] = device["DeviceKey"]

        payload = {
            "AuthFlow": "REFRESH_TOKEN_AUTH",
            "ClientId": AWS_CLIENT_ID,
            "AuthParameters": auth_params,
        }

        headers = {**DEFAULT_HEADERS, **AUTH_HEADERS}

        try:
            response = requests.post(
                URLS["auth"],
                json=payload,
                headers=headers,
                timeout=DEFAULT_TIMEOUT,
            )
        except requests.exceptions.RequestException as e:
            raise NetworkError(f"Network error during token refresh: {e}") from e

        if response.status_code == 200:
            result = response.json()

            # Guard against an unexpected response shape before accessing nested
            # keys — a missing AuthenticationResult would otherwise raise an
            # unhandled KeyError rather than a clean AuthenticationError.
            if "AuthenticationResult" not in result:
                raise AuthenticationError(f"Unexpected token refresh response shape: {result}")

            # Refresh response doesn't always include new refresh token
            if "RefreshToken" not in result["AuthenticationResult"]:
                result["AuthenticationResult"]["RefreshToken"] = self._token.refresh_token

            self._token = self._parse_auth_response(result)
            self._save_token(self._token)
            _LOGGER.info("Successfully refreshed token")
            return self._token
        elif response.status_code in (400, 401):
            _LOGGER.warning("Refresh token expired, performing new authentication")
            return self._authenticate_new()
        else:
            raise AuthenticationError(
                f"Token refresh failed with status {response.status_code}: {response.text}"
            )

    # ------------------------------------------------------------------
    # Private helpers – device remembering
    # ------------------------------------------------------------------

    def _cognito_request(self, target: str, payload: dict) -> dict:
        """Make a raw Cognito IdP API call (e.g. ConfirmDevice)."""
        headers = {
            **DEFAULT_HEADERS,
            "Content-Type": "application/x-amz-json-1.1",
            "X-Amz-Target": f"AWSCognitoIdentityProviderService.{target}",
            "X-Amz-User-Agent": "aws-amplify/5.0.4 js",
            "Referer": "https://accounts.dronemobile.com/",
        }
        try:
            response = requests.post(
                URLS["auth"], json=payload, headers=headers, timeout=DEFAULT_TIMEOUT
            )
        except requests.exceptions.RequestException as e:
            raise NetworkError(f"Network error during {target}: {e}") from e
        if response.status_code != 200:
            raise AuthenticationError(
                f"{target} failed with status {response.status_code}: {response.text}"
            )
        return response.json() if response.content else {}

    def _remember_device(self, access_token: str, device_key: str, device_group_key: str) -> None:
        """Confirm and remember a newly-issued Cognito device.

        Replicates the app's "Don't ask again on this device": generate a device
        password verifier, ``ConfirmDevice``, then mark it remembered. The
        DeviceKey is afterwards included on refresh so refreshes are not forced
        through MFA.
        """
        existing = self._load_device()
        if existing and existing.get("DeviceKey") == device_key:
            return

        device_password, verifier_config = generate_device_verifier(device_group_key, device_key)
        self._cognito_request(
            "ConfirmDevice",
            {
                "AccessToken": access_token,
                "DeviceKey": device_key,
                "DeviceName": "Home Assistant",
                "DeviceSecretVerifierConfig": verifier_config,
            },
        )
        self._cognito_request(
            "UpdateDeviceStatus",
            {
                "AccessToken": access_token,
                "DeviceKey": device_key,
                "DeviceRememberedStatus": "remembered",
            },
        )
        self._device = {
            "DeviceKey": device_key,
            "DeviceGroupKey": device_group_key,
            "DevicePassword": device_password,
        }
        self._save_device()
        _LOGGER.info("Device confirmed and remembered (DeviceKey=%s)", device_key)

    def _save_device(self) -> None:
        """Persist the remembered device next to the token."""
        if not self._device:
            return
        try:
            with open(self.device_file, "w") as f:
                json.dump(self._device, f, indent=2)
            try:
                os.chmod(self.device_file, 0o600)
            except OSError:
                pass
        except OSError as e:
            _LOGGER.warning(f"Could not save device file: {e}")

    def _load_device(self) -> dict | None:
        """Load the remembered device from disk (cached in memory)."""
        if self._device is not None:
            return self._device
        if self.device_file.exists():
            try:
                with open(self.device_file) as f:
                    self._device = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                _LOGGER.warning(f"Could not load device file: {e}")
        return self._device

    def _clear_device(self) -> None:
        """Forget the remembered device (in memory and on disk)."""
        self._device = None
        try:
            if self.device_file.exists():
                self.device_file.unlink()
        except OSError as e:
            _LOGGER.debug(f"Could not remove device file: {e}")

    # ------------------------------------------------------------------
    # Private helpers – token persistence
    # ------------------------------------------------------------------

    def _parse_auth_response(self, response: dict) -> AuthToken:
        """
        Parse authentication response and create AuthToken.

        Args:
            response: API response dictionary

        Returns:
            AuthToken object
        """
        auth_result = response["AuthenticationResult"]

        # If Cognito issued a device for this fresh login, confirm and remember
        # it so subsequent refreshes are not forced back through MFA.
        ndm = auth_result.get("NewDeviceMetadata")
        if ndm and ndm.get("DeviceKey"):
            try:
                self._remember_device(
                    auth_result["AccessToken"],
                    ndm["DeviceKey"],
                    ndm.get("DeviceGroupKey", ""),
                )
            except Exception as e:  # noqa: BLE001 - never block login on this
                _LOGGER.warning("Could not remember device (will rely on refresh token): %s", e)

        expires_in = auth_result["ExpiresIn"]
        expires_at = datetime.now() + timedelta(seconds=expires_in - TOKEN_EXPIRY_MARGIN)

        return AuthToken(
            access_token=auth_result["AccessToken"],
            id_token=auth_result["IdToken"],
            refresh_token=auth_result["RefreshToken"],
            token_type=auth_result["TokenType"],
            expires_at=expires_at,
        )

    def _save_token(self, token: AuthToken) -> None:
        """
        Save token to file with secure permissions.

        Args:
            token: AuthToken to save
        """
        lock = filelock.FileLock(f"{self.token_file}.lock")

        try:
            with lock.acquire(timeout=10):
                with open(self.token_file, "w") as f:
                    json.dump(token.to_dict(), f, indent=2)

                # Set secure file permissions (owner read/write only)
                try:
                    os.chmod(self.token_file, 0o600)
                except OSError as e:
                    _LOGGER.warning(f"Could not set secure permissions on token file: {e}")

                _LOGGER.debug(f"Token saved to {self.token_file}")
        except filelock.Timeout:
            _LOGGER.error("Could not acquire lock to save token")

    def _load_token(self) -> AuthToken | None:
        """
        Load token from file.

        Returns:
            AuthToken if found and valid, None otherwise
        """
        # Try new location first
        if self.token_file.exists():
            try:
                with open(self.token_file) as f:
                    data = json.load(f)
                    return AuthToken.from_dict(data)
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                _LOGGER.warning(f"Could not parse token file: {e}")
                return None

        # Try migrating from legacy location
        legacy_path = Path(LEGACY_TOKEN_LOCATION)
        if legacy_path.exists():
            _LOGGER.info("Migrating token from legacy location")
            try:
                with open(legacy_path) as f:
                    data = json.load(f)
                    token = self._migrate_legacy_token(data)
                    if token:
                        self._save_token(token)
                        # Remove legacy file after successful migration
                        legacy_path.unlink()
                        return token
            except Exception as e:
                _LOGGER.warning(f"Could not migrate legacy token: {e}")

        return None

    def _migrate_legacy_token(self, data: dict) -> AuthToken | None:
        """
        Migrate token data from old format to new format.

        Args:
            data: Legacy token data

        Returns:
            AuthToken if migration successful, None otherwise
        """
        try:
            auth_result = data.get("AuthenticationResult", {})

            # Handle legacy expiry time formats
            if "expiry_time" in data:
                expires_at = datetime.fromtimestamp(data["expiry_time"])
            elif "expiry_date" in data:
                if isinstance(data["expiry_date"], (int, float)):
                    expires_at = datetime.fromtimestamp(data["expiry_date"])
                else:
                    # Can't parse, set to expired
                    expires_at = datetime.now()
            else:
                expires_at = datetime.now()

            return AuthToken(
                access_token=auth_result.get("AccessToken", ""),
                id_token=auth_result.get("IdToken", ""),
                refresh_token=auth_result.get("RefreshToken", ""),
                token_type=auth_result.get("TokenType", "Bearer"),
                expires_at=expires_at,
            )
        except (KeyError, ValueError) as e:
            _LOGGER.error(f"Failed to migrate legacy token: {e}")
            return None
