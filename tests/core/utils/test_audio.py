"""Tests for PCM and WAV audio stream resources."""

import io
import wave

import pytest

from mindor.core.component.services.model.tasks.music_generation.common import MusicGenerationTaskAction
from mindor.core.utils.audio import PcmStreamResource, WavStreamResource


@pytest.fixture
def anyio_backend():
    """Configure anyio to use asyncio backend."""
    return "asyncio"


# ---- Helpers ----

async def collect_stream(stream):
    """Collect all bytes from an async stream resource."""
    chunks = []
    async with stream:
        async for chunk in stream:
            chunks.append(chunk)
    return b"".join(chunks)


# ---- Tests ----

def test_encode_pcm16_transposes_channel_first_samples():
    """Test that PCM16 encoding transposes channel-first samples correctly."""
    frames, channels = MusicGenerationTaskAction.__new__(MusicGenerationTaskAction)._encode_samples_to_pcm16(
        [[0.0, 0.25, 0.5], [0.0, -0.25, -0.5]]
    )

    assert channels == 2
    assert len(frames) == 3 * 2 * 2


@pytest.mark.anyio
async def test_wav_stream_resource_wraps_pcm_samples():
    """Test that WavStreamResource wraps PCM samples into valid WAV data."""
    frames, channels = MusicGenerationTaskAction.__new__(MusicGenerationTaskAction)._encode_samples_to_pcm16(
        [[0.0, 0.25, 0.5], [0.0, -0.25, -0.5]]
    )
    stream = WavStreamResource(PcmStreamResource(frames, {
        "sample_rate": "48000",
        "channels": str(channels),
        "bit_depth": "16",
    }))
    data = await collect_stream(stream)

    with wave.open(io.BytesIO(data), "rb") as wav:
        assert wav.getnchannels() == 2
        assert wav.getsampwidth() == 2
        assert wav.getframerate() == 48000
        assert wav.getnframes() == 3
