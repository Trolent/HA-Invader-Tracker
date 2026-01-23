"""Custom exceptions for Invader Tracker integration."""


class InvaderTrackerError(Exception):
    """Base exception for all Invader Tracker errors."""


# === Authentication Errors ===
class AuthenticationError(InvaderTrackerError):
    """UID is invalid or expired."""


# === Connection Errors ===
class InvaderTrackerConnectionError(InvaderTrackerError):
    """Failed to connect to external service."""


class FlashInvaderConnectionError(InvaderTrackerConnectionError):
    """Failed to connect to Flash Invader API."""


class InvaderSpotterConnectionError(InvaderTrackerConnectionError):
    """Failed to connect to invader-spotter.art."""


# === Data Errors ===
class DataError(InvaderTrackerError):
    """Error processing data from external service."""


class ParseError(DataError):
    """Failed to parse response from external service."""


class InvalidResponseError(DataError):
    """Response format is unexpected."""


# === Rate Limiting ===
class RateLimitError(InvaderTrackerError):
    """Request was rate limited by external service."""

    def __init__(self, retry_after: int | None = None) -> None:
        self.retry_after = retry_after
        super().__init__(f"Rate limited. Retry after: {retry_after}s")
