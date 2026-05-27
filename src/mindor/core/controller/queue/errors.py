class BlobNotFoundError(RuntimeError):
    """Raised when a blob key referenced in a deserialization marker is missing from Redis."""
    pass

class BlobCorruptedError(RuntimeError):
    """Raised when a blob's actual size does not match the marker's expected size."""
    pass

class BlobTooLargeError(RuntimeError):
    """Raised when a serialized binary payload exceeds max_blob_size."""
    pass

class BlobUnauthorizedError(RuntimeError):
    """Raised when a blob marker's key does not match the expected prefix for the current task."""
    pass
