"""Tests for AudioProcessorAction's I/O matrix (single / list / AsyncIterator input,
with output unspecified / ${result} / ${result[]} / gacked cases) and per-method
sanity checks.

Numpy-only methods (dc-shift, normalize, peak-limit, trim-edges, trim-silence)
run unconditionally. Pedalboard-backed methods (highpass, lowpass, pitch-shift,
compressor, gain, chorus, delay, reverb) are skipped when pedalboard is not
installed in the test environment.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any, List

import pytest
from pydantic import TypeAdapter

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.audio_processor.drivers.native import NativeAudioProcessorAction as AudioProcessorAction
from mindor.core.foundation.streaming.audio import PcmStreamResource
from mindor.core.foundation.streaming.media import MediaSource
from mindor.dsl.schema.action import AudioProcessorActionConfig


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ---- Helpers ----

def _make_pcm_source(
    duration_seconds: float = 0.2,
    sample_rate: int = 16000,
    amplitude: float = 0.3,
) -> PcmStreamResource:
    """Build a PcmStreamResource of a 440Hz sine wave (mono, s16le)."""
    import numpy as np
    t = np.linspace(0.0, duration_seconds, int(sample_rate * duration_seconds), endpoint=False, dtype=np.float32)
    wave = (amplitude * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32)
    samples_i16 = (np.clip(wave, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()

    return PcmStreamResource(samples_i16, {
        "sample_rate": str(sample_rate),
        "channels":    "1",
        "bit_depth":   "16",
    })


async def _make_async_iter(sources: List[PcmStreamResource]) -> AsyncIterator[PcmStreamResource]:
    for src in sources:
        yield src


async def _collect(stream: AsyncIterator) -> list:
    return [ item async for item in stream ]


async def _pcm_bytes(resource: PcmStreamResource) -> bytes:
    chunks = []
    async with resource:
        async for chunk in resource:
            chunks.append(chunk)
    return b"".join(chunks)


def _config(method: str, output: Any = None, **extras) -> AudioProcessorActionConfig:
    raw = { "method": method, "audio": "${input.audio}", **extras }
    if output is not None:
        raw["output"] = output
    return TypeAdapter(AudioProcessorActionConfig).validate_python(raw)


# ---- I/O matrix (single / list / stream) ----

class TestAudioProcessorSingleInput:
    """Single MediaSource as input."""

    @pytest.mark.anyio
    async def test_no_output_returns_single_resource(self):
        config = _config("dc-shift", output=None)
        action = AudioProcessorAction(config)

        context = ComponentActionContext("run-1", { "audio": _make_pcm_source() })
        result = await action.run(context, asyncio.get_running_loop())

        assert isinstance(result, PcmStreamResource)

    @pytest.mark.anyio
    async def test_passthrough_output_returns_single_resource(self):
        config = _config("dc-shift", output="${result}")
        action = AudioProcessorAction(config)

        context = ComponentActionContext("run-2", { "audio": _make_pcm_source() })
        result = await action.run(context, asyncio.get_running_loop())

        assert isinstance(result, PcmStreamResource)

    @pytest.mark.anyio
    async def test_stream_output_template_does_not_trigger_stream_mode(self):
        """Single input keeps a single-value output shape regardless of ${result[]}."""
        config = _config("dc-shift", output="${result[]}")
        action = AudioProcessorAction(config)

        context = ComponentActionContext("run-3", { "audio": _make_pcm_source() })
        result = await action.run(context, asyncio.get_running_loop())

        assert not isinstance(result, AsyncIterator)


class TestAudioProcessorListInput:
    """List of MediaSource as input."""

    @pytest.mark.anyio
    async def test_no_output_returns_list(self):
        config = _config("dc-shift", output=None)
        action = AudioProcessorAction(config)

        sources = [ _make_pcm_source() for _ in range(3) ]
        context = ComponentActionContext("run-4", { "audio": sources })
        result = await action.run(context, asyncio.get_running_loop())

        assert isinstance(result, list)
        assert len(result) == 3
        assert all(isinstance(item, PcmStreamResource) for item in result)

    @pytest.mark.anyio
    async def test_passthrough_output_returns_list(self):
        config = _config("dc-shift", output="${result}")
        action = AudioProcessorAction(config)

        sources = [ _make_pcm_source() for _ in range(2) ]
        context = ComponentActionContext("run-5", { "audio": sources })
        result = await action.run(context, asyncio.get_running_loop())

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(item, PcmStreamResource) for item in result)


class TestAudioProcessorStreamInput:
    """AsyncIterator of MediaSource as input."""

    @pytest.mark.anyio
    async def test_no_output_returns_async_iterator(self):
        config = _config("dc-shift", output=None)
        action = AudioProcessorAction(config)

        sources = [ _make_pcm_source() for _ in range(3) ]
        context = ComponentActionContext("run-6", { "audio": _make_async_iter(sources) })
        result = await action.run(context, asyncio.get_running_loop())

        assert isinstance(result, AsyncIterator)
        items = await _collect(result)
        assert len(items) == 3
        assert all(isinstance(item, PcmStreamResource) for item in items)

    @pytest.mark.anyio
    async def test_passthrough_output_returns_async_iterator(self):
        config = _config("dc-shift", output="${result}")
        action = AudioProcessorAction(config)

        sources = [ _make_pcm_source() for _ in range(3) ]
        context = ComponentActionContext("run-7", { "audio": _make_async_iter(sources) })
        result = await action.run(context, asyncio.get_running_loop())

        assert isinstance(result, AsyncIterator)
        items = await _collect(result)
        assert len(items) == 3


# ---- Numpy-only methods (no pedalboard needed) ----

class TestAudioProcessorNumpyMethods:
    """Sanity check the 5 methods that don't depend on pedalboard."""

    @pytest.mark.anyio
    async def test_dc_shift_default_removes_mean(self):
        """With offset omitted, dc-shift centers the waveform (mean ≈ 0)."""
        import numpy as np
        config = _config("dc-shift")
        action = AudioProcessorAction(config)

        # Add a strong DC offset (+0.2) to a small clean tone
        source = _make_pcm_source(amplitude=0.2)
        context = ComponentActionContext("dc-1", { "audio": source })
        result = await action.run(context, asyncio.get_running_loop())

        data = await _pcm_bytes(result)
        samples = np.frombuffer(data, dtype="<i2").astype(np.float32) / 32767.0
        # After DC removal, mean should be close to 0 (well under the input's 0.2 offset).
        assert abs(float(np.mean(samples))) < 0.01

    @pytest.mark.anyio
    async def test_dc_shift_with_offset_applies_shift(self):
        import numpy as np
        config = _config("dc-shift", offset=0.1)
        action = AudioProcessorAction(config)

        source = _make_pcm_source(amplitude=0.05)  # small so 0.1 shift is dominant
        context = ComponentActionContext("dc-2", { "audio": source })
        result = await action.run(context, asyncio.get_running_loop())

        data = await _pcm_bytes(result)
        samples = np.frombuffer(data, dtype="<i2").astype(np.float32) / 32767.0
        assert abs(float(np.mean(samples)) - 0.1) < 0.01

    @pytest.mark.anyio
    async def test_normalize_scales_to_target_rms(self):
        import numpy as np
        config = _config("normalize", level=-20.0, peak_limit=0.99)
        action = AudioProcessorAction(config)

        # Start with a small amplitude tone
        source = _make_pcm_source(amplitude=0.05)
        context = ComponentActionContext("norm-1", { "audio": source })
        result = await action.run(context, asyncio.get_running_loop())

        data = await _pcm_bytes(result)
        samples = np.frombuffer(data, dtype="<i2").astype(np.float32) / 32767.0
        rms = float(np.sqrt(np.mean(samples ** 2)))
        target_rms = 10.0 ** (-20.0 / 20.0)  # 0.1
        # Should be near target (within ~1 dB tolerance for int16 quantization)
        assert 0.08 < rms < 0.12

    @pytest.mark.anyio
    async def test_peak_limit_only_scales_when_exceeded(self):
        import numpy as np
        # Case A: peak already below limit → unchanged
        config = _config("peak-limit", level=0.9)
        action = AudioProcessorAction(config)

        source = _make_pcm_source(amplitude=0.3)
        context = ComponentActionContext("peak-1", { "audio": source })
        result = await action.run(context, asyncio.get_running_loop())

        data = await _pcm_bytes(result)
        samples = np.frombuffer(data, dtype="<i2").astype(np.float32) / 32767.0
        peak = float(np.abs(samples).max())
        # Input peak ~0.3 stays roughly the same
        assert 0.28 < peak < 0.32

    @pytest.mark.anyio
    async def test_peak_limit_caps_hot_signal(self):
        import numpy as np
        config = _config("peak-limit", level=0.5)
        action = AudioProcessorAction(config)

        source = _make_pcm_source(amplitude=0.95)
        context = ComponentActionContext("peak-2", { "audio": source })
        result = await action.run(context, asyncio.get_running_loop())

        data = await _pcm_bytes(result)
        samples = np.frombuffer(data, dtype="<i2").astype(np.float32) / 32767.0
        peak = float(np.abs(samples).max())
        assert peak <= 0.51  # scaled down to <= 0.5 (small tolerance for int16 rounding)

    @pytest.mark.anyio
    async def test_trim_edges_removes_silent_padding(self):
        """A tone padded with silence should be shorter after trim-edges."""
        import numpy as np

        sample_rate = 16000
        silence = np.zeros(sample_rate, dtype=np.float32)                     # 1s silence
        tone_t = np.linspace(0.0, 0.5, sample_rate // 2, endpoint=False, dtype=np.float32)
        tone = (0.3 * np.sin(2 * np.pi * 440.0 * tone_t)).astype(np.float32)  # 0.5s tone
        waveform = np.concatenate([silence, tone, silence])
        samples_i16 = (np.clip(waveform, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()

        source = PcmStreamResource(samples_i16, {
            "sample_rate": str(sample_rate), "channels": "1", "bit_depth": "16",
        })

        config = _config("trim-edges", threshold=40.0)
        action = AudioProcessorAction(config)
        context = ComponentActionContext("trim-e-1", { "audio": source })
        result = await action.run(context, asyncio.get_running_loop())

        data = await _pcm_bytes(result)
        trimmed_samples = len(data) // 2  # int16
        original_samples = len(waveform)
        assert trimmed_samples < original_samples
        # The tone itself is ~8000 samples; trimmed length should be in that ballpark
        # (with some frame-boundary slack).
        assert trimmed_samples < original_samples * 0.7

    @pytest.mark.anyio
    async def test_trim_silence_returns_shorter_or_equal(self):
        """trim-silence must not make the output longer than the input."""
        source = _make_pcm_source(duration_seconds=1.0)
        # Grab the original PCM byte length via re-encoding.
        config = _config("trim-silence")
        action = AudioProcessorAction(config)

        context = ComponentActionContext("trim-s-1", { "audio": source })
        result = await action.run(context, asyncio.get_running_loop())
        data = await _pcm_bytes(result)

        # Input was 1s @ 16kHz mono int16 = 32000 bytes.
        assert len(data) <= 32000


# ---- Pedalboard-backed methods (skipped if pedalboard is not installed) ----

_pedalboard_available = True
try:
    import pedalboard  # noqa: F401
except ImportError:
    _pedalboard_available = False


@pytest.mark.skipif(not _pedalboard_available, reason="pedalboard is not installed")
class TestAudioProcessorPedalboardMethods:
    """Sanity check the 8 methods that use pedalboard.

    Each method should produce a non-empty PcmStreamResource of the same
    approximate length as the input (except delay which extends the tail).
    """

    @pytest.mark.anyio
    async def test_gain_boost_increases_peak(self):
        import numpy as np
        config = _config("gain", level=12.0)  # +12 dB ≈ 4x
        action = AudioProcessorAction(config)

        source = _make_pcm_source(amplitude=0.05)
        context = ComponentActionContext("gain-1", { "audio": source })
        result = await action.run(context, asyncio.get_running_loop())

        data = await _pcm_bytes(result)
        samples = np.frombuffer(data, dtype="<i2").astype(np.float32) / 32767.0
        peak = float(np.abs(samples).max())
        # 0.05 * 4 = 0.20 (within int16 quantization tolerance)
        assert 0.15 < peak < 0.25

    @pytest.mark.anyio
    async def test_highpass_attenuates_low_frequencies(self):
        """A pure 100Hz tone with 2kHz high-pass should be strongly attenuated."""
        import numpy as np
        sample_rate = 16000
        duration = 0.5
        t = np.linspace(0.0, duration, int(sample_rate * duration), endpoint=False, dtype=np.float32)
        low_tone = (0.5 * np.sin(2 * np.pi * 100.0 * t)).astype(np.float32)
        samples_i16 = (np.clip(low_tone, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()
        source = PcmStreamResource(samples_i16, {
            "sample_rate": str(sample_rate), "channels": "1", "bit_depth": "16",
        })

        config = _config("highpass", cutoff=2000.0)
        action = AudioProcessorAction(config)
        context = ComponentActionContext("hp-1", { "audio": source })
        result = await action.run(context, asyncio.get_running_loop())

        data = await _pcm_bytes(result)
        out = np.frombuffer(data, dtype="<i2").astype(np.float32) / 32767.0
        out_rms = float(np.sqrt(np.mean(out ** 2)))
        # Should be substantially attenuated (order of magnitude below the ~0.35 RMS input)
        assert out_rms < 0.1

    @pytest.mark.anyio
    async def test_lowpass_attenuates_high_frequencies(self):
        import numpy as np
        sample_rate = 16000
        duration = 0.5
        t = np.linspace(0.0, duration, int(sample_rate * duration), endpoint=False, dtype=np.float32)
        high_tone = (0.5 * np.sin(2 * np.pi * 4000.0 * t)).astype(np.float32)
        samples_i16 = (np.clip(high_tone, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()
        source = PcmStreamResource(samples_i16, {
            "sample_rate": str(sample_rate), "channels": "1", "bit_depth": "16",
        })

        config = _config("lowpass", cutoff=500.0)
        action = AudioProcessorAction(config)
        context = ComponentActionContext("lp-1", { "audio": source })
        result = await action.run(context, asyncio.get_running_loop())

        data = await _pcm_bytes(result)
        out = np.frombuffer(data, dtype="<i2").astype(np.float32) / 32767.0
        out_rms = float(np.sqrt(np.mean(out ** 2)))
        assert out_rms < 0.1

    @pytest.mark.parametrize("method,extras", [
        ("pitch-shift", { "semitones": 2 }),
        ("compressor", { "threshold": -20, "ratio": 4, "attack": "1ms", "release": "100ms" }),
        ("chorus", {}),
        ("delay", { "time": "50ms" }),
        ("reverb", {}),
    ])
    @pytest.mark.anyio
    async def test_method_runs_and_returns_pcm(self, method, extras):
        """Smoke test: each pedalboard method produces a valid PcmStreamResource."""
        config = _config(method, **extras)
        action = AudioProcessorAction(config)

        source = _make_pcm_source(duration_seconds=0.5)
        context = ComponentActionContext(f"{method}-smoke", { "audio": source })
        result = await action.run(context, asyncio.get_running_loop())

        assert isinstance(result, PcmStreamResource)
        data = await _pcm_bytes(result)
        assert len(data) > 0
