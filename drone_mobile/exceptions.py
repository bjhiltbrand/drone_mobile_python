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
