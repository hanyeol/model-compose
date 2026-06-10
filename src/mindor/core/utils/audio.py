from typing import Union, Optional, Dict, Any
from collections.abc import AsyncIterator
from .streaming import StreamResource, BytesStreamResource
import struct

_AUDIO_CONTENT_TYPE_MAP: Dict[str, str] = {
    "wav":  "audio/wav",
    "mp3":  "audio/mpeg",
    "aac":  "audio/aac",
    "m4a":  "audio/mp4",
    "mp4":  "audio/mp4",
    "flac": "audio/flac",
    "ogg":  "audio/ogg",
    "opus": "audio/opus",
    "webm": "audio/webm",
    "pcm":  "audio/pcm",
}

class PcmStreamResource(StreamResource):
    def __init__(
        self,
        samples: Union[StreamResource, bytes],
        attrs: Optional[Dict[str, Any]] = None,
        filename: Optional[str] = None,
    ):
        super().__init__("audio/pcm", filename)

        self.samples: StreamResource = samples if isinstance(samples, StreamResource) else BytesStreamResource(samples)
        self.attrs: Dict[str, Any] = attrs or {}

    async def close(self) -> None:
        await self.samples.close()

    async def _iterate_stream(self) -> AsyncIterator[bytes]:
        async for chunk in self.samples:
            yield chunk

class WavStreamResource(StreamResource):
    def __init__(
        self,
        source: Union[StreamResource, bytes],
        attrs: Optional[Dict[str, Any]] = None,
        filename: Optional[str] = None,
    ):
        super().__init__("audio/wav", filename)

        if isinstance(source, PcmStreamResource):
            attrs = attrs if attrs is not None else source.attrs
            source = source.samples
            is_raw_samples = True
        else:
            is_raw_samples = attrs is not None

        self.source: StreamResource = source if isinstance(source, StreamResource) else BytesStreamResource(source)
        self.attrs: Dict[str, Any] = attrs or {}

        self._is_raw_samples = is_raw_samples

    async def close(self) -> None:
        await self.source.close()

    async def _iterate_stream(self) -> AsyncIterator[bytes]:
        if self._is_raw_samples:
            yield self._build_header()
        async for chunk in self.source:
            yield chunk

    def _build_header(self) -> bytes:
        sample_rate = int(self.attrs.get("sample_rate", 44100))
        channels    = int(self.attrs.get("channels", 1))
        bit_depth   = int(self.attrs.get("bit_depth", 16))
        byte_rate   = sample_rate * channels * bit_depth // 8
        block_align = channels * bit_depth // 8

        # Streaming WAV: use 0xFFFFFFFF for unknown chunk sizes (RIFF convention).
        # Most decoders (ffmpeg, VLC, browsers) read until EOF instead of trusting the size.
        return (
            b"RIFF" + struct.pack("<I", 0xFFFFFFFF) + b"WAVE"
            + b"fmt " + struct.pack("<I", 16)
            + struct.pack("<HHIIHH", 1, channels, sample_rate, byte_rate, block_align, bit_depth)
            + b"data" + struct.pack("<I", 0xFFFFFFFF)
        )

class AudioStreamResource(StreamResource):
    def __init__(
        self,
        source: Union[StreamResource, bytes],
        format: Optional[str] = None,
        attrs: Optional[Dict[str, Any]] = None,
        filename: Optional[str] = None,
    ):
        super().__init__(self._resolve_content_type(format), filename, size=self._resolve_size(source))

        self.source: StreamResource = source if isinstance(source, StreamResource) else BytesStreamResource(source)
        self.format: str = format
        self.attrs: Dict[str, Any] = attrs or {}

    async def close(self) -> None:
        await self.source.close()

    async def _iterate_stream(self) -> AsyncIterator[bytes]:
        async for chunk in self.source:
            yield chunk

    @staticmethod
    def _resolve_content_type(format: Optional[str]) -> str:
        if format:
            return _AUDIO_CONTENT_TYPE_MAP.get(format.lower(), "application/octet-stream")
        return "application/octet-stream"

    @staticmethod
    def _resolve_size(source: Union[StreamResource, bytes]) -> Optional[int]:
        return source.size if isinstance(source, StreamResource) else len(source)
