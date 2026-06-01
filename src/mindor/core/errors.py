from typing import Optional

class TaskError(ValueError):
    """ValueError variant carrying a stable error code for API responses."""

    code: str = "INVALID_REQUEST"

    def __init__(self, message: str, code: Optional[str] = None):
        super().__init__(message)
        if code is not None:
            self.code = code

class ShutdownError(RuntimeError):
    """Raised when an operation is attempted while the service is shutting down."""
    pass