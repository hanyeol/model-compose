from typing import Union, Optional, Dict
from collections.abc import AsyncIterator
from .streaming import StreamResource, BytesStreamResource, read_stream_to_buffer
import wave, io

class PcmStreamResource(StreamResource):
    def __init__(self, samples: Union[StreamResource, bytes], attrs: Optional[Dict[str, str]] = None):
        super().__init__("audio/pcm", None)

        self.samples: StreamResource = samples if isinstance(samples, StreamResource) else BytesStreamResource(samples)
        self.attrs: Optional[Dict[str, str]] = attrs

    async def close(self) -> None:
        await self.samples.close()

    async def _iterate_stream(self) -> AsyncIterator[bytes]:
        async for chunk in self.samples:
            yield chunk

class WavStreamResource(StreamResource):
    def __init__(self, source: Union[StreamResource, bytes]):
        super().__init__("audio/wav", None)

        self.source: StreamResource = source if isinstance(source, StreamResource) else BytesStreamResource(source)
        self.buffer: Optional[io.BytesIO] = None

    async def close(self) -> None:
        if self.buffer:
            self.buffer.close()
            self.buffer = None

    async def _iterate_stream(self) -> AsyncIterator[bytes]:
        if not self.buffer:
            self.buffer = await self._build_buffer()

        while True:
            chunk = self.buffer.read(8192)
            if not chunk:
                break
            yield chunk

    async def _build_buffer(self) -> io.BytesIO:
        if isinstance(self.source, PcmStreamResource):
            return await self._read_pcm_to_buffer(self.source)

        return await read_stream_to_buffer(self.source)

    async def _read_pcm_to_buffer(self, source: PcmStreamResource) -> io.BytesIO:
        frames = bytearray()
        async for chunk in source:
            frames.extend(chunk)

        attrs = source.attrs or {}
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav:
            wav.setnchannels(int(attrs.get("channels", 1)))
            wav.setsampwidth(int(attrs.get("bit_depth", 16)) // 8)
            wav.setframerate(int(attrs.get("sample_rate", 44100)))
            wav.writeframes(frames)
        buffer.seek(0)

        return buffer
