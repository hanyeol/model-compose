from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional
from collections.abc import AsyncIterator
from .resources import StreamResource
import io

if TYPE_CHECKING:
    import numpy as np

class WaveformStreamResource(StreamResource):
    """Stream a time-series waveform as encoded bytes, computed lazily on first iteration.

    Domain-neutral: subclasses decide how the waveform is serialized (e.g.
    audio PCM, biosignal frames, RF I/Q) by implementing ``_encode_bytes``.
    """
    def __init__(self, waveform: np.ndarray, content_type: Optional[str] = None, chunk_size: int = 8192):
        super().__init__(content_type)

        self.waveform: np.ndarray = waveform
        self.chunk_size: int = chunk_size

        self._encoded_bytes: Optional[bytes] = None
        self._stream: Optional[io.BytesIO] = None

    async def close(self) -> None:
        if self._stream:
            self._stream.close()
            self._stream = None

        self._encoded_bytes = None

    async def _iterate_stream(self) -> AsyncIterator[bytes]:
        if self._encoded_bytes is None:
            self._encoded_bytes = self._encode_bytes(self.waveform)

        if not self._stream:
            self._stream = io.BytesIO(self._encoded_bytes)

        while True:
            chunk = self._stream.read(self.chunk_size)
            if not chunk:
                break
            yield chunk

    def _encode_bytes(self, waveform: np.ndarray) -> bytes:
        return waveform.tobytes()
