"""Tests for ``mindor.core.foundation.streaming.image.load_image_from_stream``.

Covers both the contract (bytes -> PIL.Image) and the non-blocking behaviour
guaranteed by wrapping ``PILImage.open`` in ``asyncio.to_thread``.
"""

from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image as PILImage

from mindor.core.foundation.streaming.bytes import BytesStreamResource
from mindor.core.foundation.streaming.image import load_image_from_stream
from mindor.core.foundation.streaming.resources import StreamResource

from tests.async_helpers import assert_does_not_block


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ---- Helpers ----

class ChunkedBytesStream(StreamResource):
    """StreamResource that yields fixed-size chunks from a bytes buffer."""
    def __init__(self, data: bytes, chunk_size: int = 8192):
        super().__init__("application/octet-stream", None)
        self._data = data
        self._chunk_size = chunk_size

    async def close(self) -> None:
        pass

    async def _iterate_stream(self):
        for i in range(0, len(self._data), self._chunk_size):
            yield self._data[i:i + self._chunk_size]


def _png_bytes(width: int, height: int, mode: str = "RGB", noisy: bool = False) -> bytes:
    """Create PNG bytes of a given size. ``noisy=True`` fills with random data
    so the encoder can't trivially compress it (making decode take real time)."""
    if noisy:
        rng = np.random.default_rng(seed=42)
        channels = {"RGB": 3, "RGBA": 4, "L": 1}[mode]
        arr = rng.integers(0, 256, size=(height, width, channels), dtype=np.uint8)
        if channels == 1:
            arr = arr[..., 0]
        image = PILImage.fromarray(arr, mode=mode)
    else:
        image = PILImage.new(mode, (width, height), color=(128, 200, 50) if mode == "RGB" else 128)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _jpeg_bytes(width: int, height: int) -> bytes:
    image = PILImage.new("RGB", (width, height), color=(200, 100, 50))
    buf = io.BytesIO()
    image.save(buf, format="JPEG")
    return buf.getvalue()


# ---- Contract tests ----

class TestLoadImageFromStreamContract:
    @pytest.mark.anyio
    async def test_small_png_returns_pil_image_with_correct_size_and_mode(self):
        data = _png_bytes(64, 48, mode="RGB")
        stream = BytesStreamResource(data)

        image = await load_image_from_stream(stream)

        assert isinstance(image, PILImage.Image)
        assert image.size == (64, 48)
        assert image.mode == "RGB"

    @pytest.mark.anyio
    async def test_jpeg_bytes_returns_pil_image(self):
        data = _jpeg_bytes(80, 60)
        stream = BytesStreamResource(data)

        image = await load_image_from_stream(stream)

        assert isinstance(image, PILImage.Image)
        assert image.size == (80, 60)
        # JPEG always decodes to RGB (or L, CMYK, etc.); our fixture is RGB.
        assert image.mode == "RGB"

    @pytest.mark.anyio
    async def test_chunked_stream_reassembles_correctly(self):
        data = _png_bytes(100, 100, mode="RGBA")
        stream = ChunkedBytesStream(data, chunk_size=37)  # deliberately awkward size

        image = await load_image_from_stream(stream)

        assert isinstance(image, PILImage.Image)
        assert image.size == (100, 100)
        assert image.mode == "RGBA"

    @pytest.mark.anyio
    async def test_empty_stream_raises(self):
        stream = BytesStreamResource(b"")

        with pytest.raises(Exception):  # PIL.UnidentifiedImageError is a subclass of OSError
            await load_image_from_stream(stream)


# ---- Non-blocking test ----

class TestLoadImageFromStreamDoesNotBlock:
    @pytest.mark.anyio
    async def test_large_png_decode_does_not_block(self):
        # 2000x2000 noisy PNG => encoded blob is a few MB and takes real CPU time to decode.
        width, height = 2000, 2000
        data = _png_bytes(width, height, mode="RGB", noisy=True)
        stream = BytesStreamResource(data)

        image = await assert_does_not_block(load_image_from_stream(stream))

        assert isinstance(image, PILImage.Image)
        assert image.size == (width, height)
        assert image.mode == "RGB"
