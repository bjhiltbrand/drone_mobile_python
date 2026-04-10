"""Custom exceptions for the DroneMobile library."""


class DroneMobileException(Exception):
    """Base exception for all DroneMobile errors."""

    pass


class AuthenticationError(DroneMobileException):
    """Raised when authentication fails."""

    pass


class TokenExpiredError(AuthenticationError):
    """Raised when the access token has expired."""

    pass


class MFARequiredError(AuthenticationError):
    """Raised when MFA is required but no code provider is configured.

    Catch this to prompt the user for their OTP, then re-authenticate by
    passing an ``mfa_callback`` to ``AuthenticationManager``.

    Example::

        from drone_mobile.auth import AuthenticationManager
        from drone_mobile.exceptions import MFARequiredError

        def ask_user(challenge_name: str) -> str:
            return input(f"Enter {challenge_name} code: ").strip()

        auth = AuthenticationManager(user, password, mfa_callback=ask_user)
    """

    def __init__(self, challenge_name: str) -> None:
        super().__init__(
            f"MFA challenge '{challenge_name}' is required. "
            "Pass an mfa_callback to AuthenticationManager."
        )
        self.challenge_name = challenge_name


class InvalidCredentialsError(AuthenticationError):
    """Raised when username or password is incorrect."""

    pass


class APIError(DroneMobileException):
    """Raised when the API returns an error response."""

    def __init__(
        self, message: str, status_code: int | None = None, response_data: dict | None = None
    ):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data


class CommandFailedError(APIError):
    """Raised when a vehicle command fails to execute."""

    pass


class VehicleNotFoundError(DroneMobileException):
    """Raised when a vehicle is not found."""

    pass


class InvalidCommandError(DroneMobileException):
    """Raised when an invalid command is specified."""

    pass


class RateLimitError(APIError):
    """Raised when API rate limit is exceeded."""

    pass


class NetworkError(DroneMobileException):
    """Raised when a network error occurs."""

    pass
