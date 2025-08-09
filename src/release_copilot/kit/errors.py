class ConfigError(Exception):
    """Raised for missing or invalid configuration."""


class ApiError(Exception):
    """Raised when an API request fails."""


class RecoverableError(Exception):
    """Raised for errors that may succeed on retry."""
