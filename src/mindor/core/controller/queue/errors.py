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

class UnsupportedProtocolError(RuntimeError):
    """Raised when a queue message's `protocol` field is not the expected version."""
    pass

class StreamKindMismatchError(TypeError):
    """Raised when a stream chunk's Python type does not match the declared StreamKind."""
    pass

class StreamAbortError(RuntimeError):
    """Raised on the consumer side when a stream is terminated with an `abort` event."""
    pass
