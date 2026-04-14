class ConfigurationError(Exception):
    """Raised when runtime configuration is invalid."""


class RiskRejected(Exception):
    """Raised when the risk manager blocks an order."""


class ExchangeUnavailableError(Exception):
    """Raised when the exchange adapter cannot serve the request."""


class DuplicateSignalError(Exception):
    """Raised when the executor detects a duplicate signal."""

