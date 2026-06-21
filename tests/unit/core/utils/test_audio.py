"""Tests for PCM and WAV audio stream resources."""

import io
import struct
import wave

import pytest

from mindor.core.component.services.model.tasks.music_generation.common import MusicGenerationTaskAction
from mindor.core.utils.streaming.audio import PcmStreamResource, WavStreamResource


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


async def collect_stream_chunks(stream):
    """Collect chunks (not joined) from an async stream resource."""
    chunks = []
    async with stream:
        async for chunk in stream:
            chunks.append(chunk)
    return chunks


# ---- Tests ----

def test_encode_pcm16_transposes_channel_first_samples():
    """Test that PCM16 encoding transposes channel-first samples correctly."""
    frames, channels = MusicGenerationTaskAction.__new__(MusicGenerationTaskAction)._encode_samples_to_pcm16(
        [[0.0, 0.25, 0.5], [0.0, -0.25, -0.5]]
    )

    assert channels == 2
    assert len(frames) == 3 * 2 * 2


@pytest.mark.anyio
async def test_wav_stream_resource_emits_header_then_samples():
    """Streaming WAV: first chunk is the 44-byte RIFF header, the rest is PCM verbatim."""
    frames, channels = MusicGenerationTaskAction.__new__(MusicGenerationTaskAction)._encode_samples_to_pcm16(
        [[0.0, 0.25, 0.5], [0.0, -0.25, -0.5]]
    )
    stream = WavStreamResource(PcmStreamResource(frames, {
        "sample_rate": "48000",
        "channels": str(channels),
        "bit_depth": "16",
    }))
    chunks = await collect_stream_chunks(stream)

    # First chunk is the WAV header (44 bytes), the rest is the PCM payload as-is.
    assert len(chunks) >= 2
    assert len(chunks[0]) == 44
    assert chunks[0][:4] == b"RIFF"
    assert chunks[0][8:12] == b"WAVE"
    assert b"".join(chunks[1:]) == frames


@pytest.mark.anyio
async def test_wav_stream_resource_header_fields_match_attrs():
    """The emitted WAV header encodes the sample_rate / channels / bit_depth from attrs."""
    frames, channels = MusicGenerationTaskAction.__new__(MusicGenerationTaskAction)._encode_samples_to_pcm16(
        [[0.0, 0.25, 0.5], [0.0, -0.25, -0.5]]
    )
    stream = WavStreamResource(PcmStreamResource(frames, {
        "sample_rate": "48000",
        "channels": str(channels),
        "bit_depth": "16",
    }))
    data = await collect_stream(stream)

    # Decoders (ffmpeg/VLC/browsers) treat 0xFFFFFFFF as unknown-size and read until EOF.
    # Python's `wave` module reports nframes as int(size/byte_per_frame) which becomes nonsensical —
    # we deliberately do NOT assert nframes here. We do check the other header fields are correct.
    with wave.open(io.BytesIO(data), "rb") as wav:
        assert wav.getnchannels() == 2
        assert wav.getsampwidth() == 2
        assert wav.getframerate() == 48000


@pytest.mark.anyio
async def test_wav_stream_resource_uses_streaming_size_marker():
    """RIFF and data chunk sizes are 0xFFFFFFFF (streaming WAV convention)."""
    pcm = PcmStreamResource(b"\x00\x00\x00\x00", {
        "sample_rate": 24000, "channels": 1, "bit_depth": 16,
    })
    stream = WavStreamResource(pcm)
    data = await collect_stream(stream)
    header = data[:44]

    # Offsets in a canonical PCM RIFF/WAVE header:
    #   [4:8]  = RIFF chunk size
    #   [40:44] = data chunk size
    assert struct.unpack("<I", header[4:8])[0] == 0xFFFFFFFF
    assert struct.unpack("<I", header[40:44])[0] == 0xFFFFFFFF


@pytest.mark.anyio
async def test_wav_stream_resource_passthrough_already_wav_bytes():
    """Raw bytes input is treated as already-encoded wav and emitted unchanged (no header prepended)."""
    # Build a tiny valid wav blob ourselves so we can detect that nothing extra was prepended.
    fake_wav = b"RIFF\xff\xff\xff\xffWAVE" + b"X" * 10  # not a real wav body, just a sentinel
    stream = WavStreamResource(fake_wav)
    data = await collect_stream(stream)
    assert data == fake_wav


@pytest.mark.anyio
async def test_wav_stream_resource_passthrough_already_wav_stream():
    """A non-PCM StreamResource input is passed through unchanged."""
    from mindor.core.utils.streaming.bytes import BytesStreamResource
    fake_wav = b"RIFF\xff\xff\xff\xffWAVE" + b"Y" * 16
    inner = BytesStreamResource(fake_wav, "audio/wav")
    stream = WavStreamResource(inner)
    data = await collect_stream(stream)
    assert data == fake_wav


@pytest.mark.anyio
async def test_wav_stream_resource_attrs_preserved_on_instance():
    """attrs supplied at construction time are kept on the instance."""
    fake_wav = b"RIFF\xff\xff\xff\xffWAVE"
    stream = WavStreamResource(fake_wav, attrs={"sample_rate": 22050, "channels": 1})
    assert stream.attrs == {"sample_rate": 22050, "channels": 1}


@pytest.mark.anyio
async def test_wav_stream_resource_streams_chunks_one_to_one():
    """Each PCM input chunk surfaces as a separate output chunk (no buffering)."""
    from mindor.core.utils.streaming.resources import StreamResource

    class FakePcmSource(StreamResource):
        def __init__(self, chunks):
            super().__init__("audio/pcm", None)
            self._chunks = chunks

        async def close(self):
            pass

        async def _iterate_stream(self):
            for c in self._chunks:
                yield c

    pcm_chunks = [b"\x01\x00", b"\x02\x00", b"\x03\x00"]
    pcm = PcmStreamResource(FakePcmSource(pcm_chunks), {"sample_rate": 8000, "channels": 1, "bit_depth": 16})
    stream = WavStreamResource(pcm)

    chunks = await collect_stream_chunks(stream)
    # 1 header + 3 PCM chunks, in order.
    assert len(chunks) == 1 + len(pcm_chunks)
    assert chunks[0][:4] == b"RIFF"
    assert chunks[1:] == pcm_chunks


@pytest.mark.anyio
async def test_wav_stream_resource_pcm_attrs_override():
    """Explicit attrs argument overrides attrs carried by an input PcmStreamResource."""
    frames = b"\x00\x00\x00\x00"
    pcm = PcmStreamResource(frames, {"sample_rate": 8000, "channels": 1, "bit_depth": 16})
    stream = WavStreamResource(pcm, attrs={"sample_rate": 48000, "channels": 2, "bit_depth": 16})
    data = await collect_stream(stream)
    with wave.open(io.BytesIO(data), "rb") as wav:
        assert wav.getframerate() == 48000
        assert wav.getnchannels() == 2
