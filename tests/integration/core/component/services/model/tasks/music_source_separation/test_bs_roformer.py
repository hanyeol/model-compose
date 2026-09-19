"""Integration tests for the BS-RoFormer music-source-separation driver.

Verifies the wrapper's audio pipeline (decode → chunked sliding-window inference →
PCM-encoded stem output) against a tiny, randomly-initialized BSRoformer so the
tests stay fast and offline. The point is the framework glue — separation
quality is upstream's concern.
"""

from __future__ import annotations

import math
import os
import struct
import tempfile
import wave
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock

import pytest


pytest.importorskip("torch")
pytest.importorskip("torchaudio")
pytest.importorskip("bs_roformer")
pytest.importorskip("numpy")

from bs_roformer import BSRoformer
from pydantic import TypeAdapter

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.model.tasks.music_source_separation.custom.roformer.base import (
    RoFormerMusicSourceSeparationTaskAction,
)
from mindor.core.foundation.streaming.audio import PcmStreamResource
from mindor.dsl.schema.action import BsRoFormerMusicSourceSeparationModelActionConfig


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _make_wav(duration: float, frequency: float, sample_rate: int = 44100, channels: int = 2) -> str:
    path = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    n_samples = int(sample_rate * duration)

    with wave.open(path, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        frames = bytearray()
        for i in range(n_samples):
            value = int(0.3 * 32767 * math.sin(2 * math.pi * frequency * i / sample_rate))
            frame = struct.pack("<h", value)
            frames += frame * channels
        w.writeframes(bytes(frames))
    return path


@pytest.fixture(scope="module")
def sample_stereo_wav():
    """Short stereo 440 Hz tone; long enough to require a couple of chunks."""
    path = _make_wav(duration=1.5, frequency=440.0, channels=2)
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture(scope="module")
def tiny_bs_roformer_action_factory():
    """Build a factory for RoFormerMusicSourceSeparationTaskAction wrapped around
    a tiny, randomly-initialized BSRoformer. The `freqs_per_bands` tuple is
    picked so it sums to the number of STFT bins produced by our stft params.
    """
    import torch

    # Deterministic init so overlap-add reconstruction stays consistent
    # between iterations of the test.
    torch.manual_seed(0)

    # Small STFT settings → few bins → fast forward pass on CPU.
    stft_n_fft = 512
    stft_hop_length = 128
    stft_win_length = 512

    # BSRoformer computes freqs = torch.stft(..., n_fft=stft_n_fft).shape[1]
    # which for n_fft=512 is 257. Split into two contiguous bands.
    freqs = stft_n_fft // 2 + 1  # 257
    freqs_per_bands = (128, freqs - 128)

    try:
        model = BSRoformer(
            dim=32,
            depth=1,
            stereo=True,
            num_stems=2,
            time_transformer_depth=1,
            freq_transformer_depth=1,
            heads=2,
            dim_head=16,
            flash_attn=False,
            num_residual_streams=1,
            freqs_per_bands=freqs_per_bands,
            stft_n_fft=stft_n_fft,
            stft_hop_length=stft_hop_length,
            stft_win_length=stft_win_length,
            mask_estimator_depth=1,
        )
    except Exception as e:  # pragma: no cover — upstream signature drift
        pytest.skip(f"BSRoformer construction failed: {e}")

    model.eval()
    device = torch.device("cpu")

    def _factory(config: BsRoFormerMusicSourceSeparationModelActionConfig) -> RoFormerMusicSourceSeparationTaskAction:
        return RoFormerMusicSourceSeparationTaskAction(
            config=config,
            model=model,
            sample_rate=44100,
            stereo=True,
            stem_names=["vocals", "instrumental"],
            device=device,
        )

    return _factory


def _make_context(audio_value: Any) -> ComponentActionContext:
    from mindor.core.foundation.streaming.audio import create_audio_source

    ctx = MagicMock(spec=ComponentActionContext)
    ctx.cancellation_token = None
    sources: Dict[str, Any] = {}

    def register_source(key: str, value: Any, scope: Any = None) -> None:
        sources[key] = value
    ctx.register_source = MagicMock(side_effect=register_source)

    async def render_variable(value, **kwargs):
        if isinstance(value, str):
            if value == "${result}":
                return sources.get("result")
        if hasattr(value, "model_dump"):
            return value.model_dump()
        return value

    def resolve_one(value):
        if isinstance(value, str):
            with open(value, "rb") as f:
                value = f.read()
        return create_audio_source(value)

    async def render_audio(_value):
        if isinstance(audio_value, list):
            return [resolve_one(v) for v in audio_value]
        return resolve_one(audio_value)

    ctx.render_variable = AsyncMock(side_effect=render_variable)
    ctx.render_audio = AsyncMock(side_effect=render_audio)

    async def render_scalar(value, cast, default=None):
        if value is None:
            return default
        return cast(value)
    ctx.render_scalar = AsyncMock(side_effect=render_scalar)

    return ctx


def _make_config(
    audio: Any = "${input.audio}",
    *,
    batch_size: int = 1,
    stems: Any = None,
    chunk_duration: float = 0.25,
    overlap: float = 0.25,
) -> BsRoFormerMusicSourceSeparationModelActionConfig:
    # Short chunk_duration (0.25s = 11025 samples) keeps the forward pass small.
    payload: Dict[str, Any] = {
        "audio":      audio,
        "batch_size": batch_size,
        "params": {
            "chunk_duration": chunk_duration,
            "overlap":        overlap,
        },
    }
    if stems is not None:
        payload["params"]["stems"] = stems
    return TypeAdapter(BsRoFormerMusicSourceSeparationModelActionConfig).validate_python(payload)


class TestSingleInput:
    """One audio input, multiple stems → dict of {stem_name: PcmStreamResource}."""

    @pytest.mark.anyio
    async def test_returns_dict_of_all_stems(self, sample_stereo_wav, tiny_bs_roformer_action_factory):
        config = _make_config(sample_stereo_wav)
        ctx    = _make_context(sample_stereo_wav)
        action = tiny_bs_roformer_action_factory(config)

        result = await action.run(ctx)

        assert isinstance(result, dict)
        assert set(result.keys()) == {"vocals", "instrumental"}
        for stem in result.values():
            assert isinstance(stem, PcmStreamResource)

    @pytest.mark.anyio
    async def test_stem_filter_returns_single_resource(self, sample_stereo_wav, tiny_bs_roformer_action_factory):
        # When only one stem is asked for, the action collapses the dict to
        # that single PcmStreamResource.
        config = _make_config(sample_stereo_wav, stems=["vocals"])
        ctx    = _make_context(sample_stereo_wav)
        action = tiny_bs_roformer_action_factory(config)

        result = await action.run(ctx)

        assert isinstance(result, PcmStreamResource)


class TestBatchInput:
    """A list of audios → a list of per-input results, in order."""

    @pytest.mark.anyio
    async def test_list_input_returns_list_of_dicts(self, sample_stereo_wav, tiny_bs_roformer_action_factory):
        config = _make_config(batch_size=2)
        ctx    = _make_context([sample_stereo_wav, sample_stereo_wav])
        action = tiny_bs_roformer_action_factory(config)

        result = await action.run(ctx)

        assert isinstance(result, list)
        assert len(result) == 2
        for entry in result:
            assert isinstance(entry, dict)
            assert set(entry.keys()) == {"vocals", "instrumental"}


class TestStemValidation:
    @pytest.mark.anyio
    async def test_unknown_stem_raises(self, sample_stereo_wav, tiny_bs_roformer_action_factory):
        config = _make_config(sample_stereo_wav, stems=["kick"])
        ctx    = _make_context(sample_stereo_wav)
        action = tiny_bs_roformer_action_factory(config)

        with pytest.raises(ValueError, match="not produced by this RoFormer checkpoint"):
            await action.run(ctx)
