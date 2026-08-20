"""Unit tests for the video-mixer overlay method covering the input/output shape matrix.

The video-mixer overlay method spans two orthogonal axes:
  - the batch axis (video: scalar vs list vs async iterator), and
  - the per-execution axis (overlay: 1 vs N, placement: 1 vs N).

These tests stub the real ffmpeg driver call (`_overlay`) and assert (a) how many
times the mixer invokes `_overlay`, (b) the exact `(video, overlays, placements)`
triple each invocation receives, and (c) the outer shape of the value returned
from `run()` (scalar vs list vs async iterator). ffmpeg command/filtergraph
assembly is covered elsewhere; here the concern is dispatch and shape.
"""

from __future__ import annotations

import asyncio
from typing import Any, List, Optional, Tuple

import pytest
from unittest.mock import AsyncMock, MagicMock

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.video_mixer.drivers.ffmpeg import FFmpegVideoMixerAction
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.streaming.video import VideoStreamResource
from mindor.core.foundation.variable.array import ArrayValue
from mindor.core.foundation.variable.video import VideoArrayValue
from mindor.dsl.schema.action import (
    FFmpegVideoMixerActionConfig,
    VideoMixerActionMethod,
    VideoMixerOverlayAudioMode,
    VideoMixerOverlayDurationMode,
    VideoOverlayPlacement,
)
from pydantic import TypeAdapter


_adapter = TypeAdapter(FFmpegVideoMixerActionConfig)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _fake_media(tag: str) -> MediaSource:
    """MediaSource identity is what we assert on — the underlying stream is a
    minimal FileStreamResource-like sentinel that never touches the filesystem."""
    stream = MagicMock(spec=FileStreamResource)
    stream.path = f"/tmp/{tag}"
    media = MediaSource(stream=stream, format="mp4")
    # Carry a human tag so assertion failure messages point at the right input.
    media._tag = tag  # type: ignore[attr-defined]
    return media


def _fake_result(tag: str) -> VideoStreamResource:
    """A sentinel VideoStreamResource so we can assert routing without running ffmpeg."""
    result = MagicMock(spec=VideoStreamResource)
    result._tag = tag  # type: ignore[attr-defined]
    return result


class _RenderStub:
    """Stubs the ComponentActionContext render_* surface used by VideoMixerAction.

    The video-mixer only touches four rendering methods for overlay:
    render_video (single MediaSource-shaped), render_video_array (list/array
    of MediaSource), render_scalar (for output flags), and render_array (for
    placement). We swap in fixed values so the test controls the input shape
    handed to `_prepare_input` directly.
    """

    def __init__(
        self,
        video: Any,
        overlay: Any,
        placement: Any,
        audio_mode: str = "base",
        streaming: bool = False,
    ):
        self.video = video
        self.overlay = overlay
        self.placement = placement
        self.audio_mode = audio_mode
        self.streaming = streaming

    def build(self) -> ComponentActionContext:
        context = MagicMock(spec=ComponentActionContext)
        context.cancellation_token = None
        context.register_source = MagicMock()

        async def render_variable(value, scope=None, skip_decode=False):
            return value

        async def render_scalar(value, cast, default=None):
            if value is None:
                return default
            if cast is bool:
                return bool(value)
            if cast is str:
                return str(value)
            if cast is int:
                return int(value)
            if cast is float:
                return float(value)
            return value

        async def render_video(value):
            return self.video

        async def render_video_array(value):
            return self.overlay

        async def render_array(value):
            return self.placement

        context.render_variable = AsyncMock(side_effect=render_variable)
        context.render_scalar = AsyncMock(side_effect=render_scalar)
        context.render_video = AsyncMock(side_effect=render_video)
        context.render_video_array = AsyncMock(side_effect=render_video_array)
        context.render_array = AsyncMock(side_effect=render_array)
        return context


def _make_action(
    overlay_field: Any = "pip.mp4",
    placement_field: Any = None,
    audio_mode: str = "base",
    duration_mode: Optional[str] = None,
    streaming: bool = False,
) -> Tuple[FFmpegVideoMixerAction, List[dict]]:
    """Build an overlay-method action wired to a mocked `_overlay` that captures its inputs.

    Returns (action, calls). `calls` is a list of dicts, one per `_overlay` invocation,
    holding {video, overlays, placements, params, streaming}.
    """
    raw: dict = {
        "method": "overlay",
        "video": "base.mp4",
        "overlay": overlay_field,
        "audio_mode": audio_mode,
        "streaming": streaming,
    }
    if placement_field is not None:
        raw["placement"] = placement_field
    if duration_mode is not None:
        raw["duration_mode"] = duration_mode

    config = _adapter.validate_python(raw)
    action = FFmpegVideoMixerAction(config)

    calls: List[dict] = []
    counter = {"n": 0}

    async def fake_overlay(
        video: MediaSource,
        overlays: List[MediaSource],
        placements: List[VideoOverlayPlacement],
        params: dict,
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> VideoStreamResource:
        calls.append({
            "video": video,
            "overlays": list(overlays),
            "placements": list(placements),
            "params": params,
            "streaming": streaming,
        })
        counter["n"] += 1
        return _fake_result(f"r{counter['n']}")

    action._overlay = fake_overlay  # type: ignore[method-assign]
    return action, calls


async def _drain(value: Any) -> Any:
    """Collect an async iterator into a list for shape assertions; pass-through otherwise."""
    if hasattr(value, "__aiter__"):
        return [ item async for item in value ]
    return value


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ---------------------------------------------------------------------------
# Single-base tests (video: scalar MediaSource)
# ---------------------------------------------------------------------------

class TestSingleBase:
    """`video` renders to one MediaSource. The result of `run()` should be one
    VideoStreamResource (not a list), regardless of how many overlays are stacked."""

    @pytest.mark.anyio
    async def test_single_base_single_overlay(self):
        action, calls = _make_action(overlay_field="pip.mp4")
        video = _fake_media("base")
        overlay = _fake_media("pip")
        placement = VideoOverlayPlacement()

        stub = _RenderStub(
            video=video,
            overlay=VideoArrayValue([overlay]),
            placement=ArrayValue([placement]),
        )
        result = await action.run(stub.build())

        assert isinstance(result, VideoStreamResource)
        assert len(calls) == 1
        assert calls[0]["video"] is video
        assert calls[0]["overlays"] == [overlay]
        assert calls[0]["placements"] == [placement]

    @pytest.mark.anyio
    async def test_single_base_multiple_overlays(self):
        action, calls = _make_action(
            overlay_field=["a.mp4", "b.mp4"],
            placement_field=[{"x": 10, "y": 10}, {"x": 20, "y": 20}],
        )
        video = _fake_media("base")
        overlays = [_fake_media("a"), _fake_media("b")]
        placements = [VideoOverlayPlacement(x=10, y=10), VideoOverlayPlacement(x=20, y=20)]

        stub = _RenderStub(
            video=video,
            overlay=VideoArrayValue(overlays),
            placement=ArrayValue(placements),
        )
        result = await action.run(stub.build())

        assert isinstance(result, VideoStreamResource)
        assert len(calls) == 1, "one base -> exactly one _overlay call"
        assert calls[0]["video"] is video
        assert calls[0]["overlays"] == overlays
        assert calls[0]["placements"] == placements

    @pytest.mark.anyio
    async def test_single_base_default_placement(self):
        """With no `placement` field, the DSL supplies a one-element default list."""
        action, calls = _make_action(overlay_field="pip.mp4", placement_field=None)
        video = _fake_media("base")
        overlay = _fake_media("pip")

        stub = _RenderStub(
            video=video,
            overlay=VideoArrayValue([overlay]),
            placement=ArrayValue([VideoOverlayPlacement()]),
        )
        result = await action.run(stub.build())

        assert isinstance(result, VideoStreamResource)
        assert len(calls) == 1
        assert calls[0]["placements"] == [VideoOverlayPlacement()]


# ---------------------------------------------------------------------------
# Batch-base tests (video: list of MediaSource)
# ---------------------------------------------------------------------------

class TestBatchBase:
    """`video` renders to a list of MediaSources. `run()` returns a list of
    VideoStreamResources, one per base, and `_overlay` is called once per base."""

    @pytest.mark.anyio
    async def test_batch_bases_broadcast_overlays(self):
        """With multiple bases, the same overlay set broadcasts to every base."""
        action, calls = _make_action(overlay_field=["a.mp4", "b.mp4"])
        bases = [_fake_media("base1"), _fake_media("base2")]
        overlays = [_fake_media("a"), _fake_media("b")]
        placement = VideoOverlayPlacement()

        stub = _RenderStub(
            video=bases,
            overlay=VideoArrayValue(overlays),
            placement=ArrayValue([placement]),
        )
        result = await action.run(stub.build())

        assert isinstance(result, list)
        assert len(result) == 2
        assert len(calls) == 2
        for call, base in zip(calls, bases):
            assert call["video"] is base
            assert call["overlays"] == overlays, "overlay set broadcasts across bases"
            # A single placement broadcasts across the overlays it applies to.
            assert call["placements"] == [placement, placement]

    @pytest.mark.anyio
    async def test_batch_bases_single_overlay(self):
        """Single overlay + multiple bases: each base gets that lone overlay."""
        action, calls = _make_action(overlay_field="pip.mp4")
        bases = [_fake_media(f"b{i}") for i in range(3)]
        overlay = _fake_media("pip")

        stub = _RenderStub(
            video=bases,
            overlay=VideoArrayValue([overlay]),
            placement=ArrayValue([VideoOverlayPlacement()]),
        )
        result = await action.run(stub.build())

        assert isinstance(result, list) and len(result) == 3
        assert len(calls) == 3
        for call, base in zip(calls, bases):
            assert call["video"] is base
            assert call["overlays"] == [overlay]


# ---------------------------------------------------------------------------
# Streaming-base tests (video: async iterator)
# ---------------------------------------------------------------------------

class TestStreamingBase:
    """When `video` is an async iterator, `run()` returns an async iterator of
    VideoStreamResource instead of a materialized list. `_overlay` is invoked
    lazily as the stream is consumed."""

    @pytest.mark.anyio
    async def test_streaming_bases_yields_per_base(self):
        action, calls = _make_action(overlay_field="pip.mp4")
        bases = [_fake_media(f"b{i}") for i in range(3)]
        overlay = _fake_media("pip")

        async def _base_stream():
            for base in bases:
                yield base

        stub = _RenderStub(
            video=_base_stream(),
            overlay=VideoArrayValue([overlay]),
            placement=ArrayValue([VideoOverlayPlacement()]),
        )
        result = await action.run(stub.build())

        # Streaming input returns an async generator; drain it and check shape.
        assert hasattr(result, "__aiter__"), "streaming input should yield an async iterator"
        collected = await _drain(result)
        assert len(collected) == 3
        assert len(calls) == 3
        for call, base in zip(calls, bases):
            assert call["video"] is base
            assert call["overlays"] == [overlay]


# ---------------------------------------------------------------------------
# Batch-size behavior
# ---------------------------------------------------------------------------

class TestBatchSize:
    """`batch_size` controls how the BatchSourceIterator groups bases before
    dispatching to `_process_batch`. It should not change the number or
    ordering of `_overlay` calls — each base still results in one call — but
    it does affect concurrency within a batch."""

    @pytest.mark.anyio
    async def test_batch_size_preserves_call_count_and_order(self):
        action, calls = _make_action(overlay_field="pip.mp4")
        # Force a batch_size of 2 so the 5 bases split into 2+2+1.
        action.config = action.config.model_copy(update={"batch_size": 2})

        bases = [_fake_media(f"b{i}") for i in range(5)]
        overlay = _fake_media("pip")

        stub = _RenderStub(
            video=bases,
            overlay=VideoArrayValue([overlay]),
            placement=ArrayValue([VideoOverlayPlacement()]),
        )
        result = await action.run(stub.build())

        assert isinstance(result, list) and len(result) == 5
        assert len(calls) == 5
        # Ordering must match the input regardless of batching.
        for call, base in zip(calls, bases):
            assert call["video"] is base


# ---------------------------------------------------------------------------
# DSL normalization at the schema layer
# ---------------------------------------------------------------------------

class TestDurationMode:
    """`duration_mode` is dispatched by `_resolve_params` and carried into `_overlay` via `params`.

    The shape tests already prove `_overlay` is called with the right video/overlays/placements;
    here we just verify the enum makes the round trip intact for each mode, since the FFmpeg
    filter-graph branches read it as a `VideoMixerOverlayDurationMode` instance.
    """

    @pytest.mark.anyio
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("base",     VideoMixerOverlayDurationMode.BASE),
            ("longest",  VideoMixerOverlayDurationMode.LONGEST),
            ("shortest", VideoMixerOverlayDurationMode.SHORTEST),
        ],
    )
    async def test_duration_mode_reaches_overlay(self, raw, expected):
        action, calls = _make_action(overlay_field="pip.mp4", duration_mode=raw)
        video = _fake_media("base")
        overlay = _fake_media("pip")

        stub = _RenderStub(
            video=video,
            overlay=VideoArrayValue([overlay]),
            placement=ArrayValue([VideoOverlayPlacement()]),
        )
        await action.run(stub.build())

        assert calls[0]["params"]["duration_mode"] == expected

    @pytest.mark.anyio
    async def test_duration_mode_defaults_to_base_when_omitted(self):
        action, calls = _make_action(overlay_field="pip.mp4")
        video = _fake_media("base")
        overlay = _fake_media("pip")

        stub = _RenderStub(
            video=video,
            overlay=VideoArrayValue([overlay]),
            placement=ArrayValue([VideoOverlayPlacement()]),
        )
        await action.run(stub.build())

        assert calls[0]["params"]["duration_mode"] == VideoMixerOverlayDurationMode.BASE


class TestBuildOverlayFilterDuration:
    """Direct tests on `_build_overlay_filter` verify filter-graph strings per duration mode."""

    def _one_placement(self):
        return [ FFmpegVideoMixerAction._resolve_overlay_filter_params(VideoOverlayPlacement(x=10, y=10)) ]

    def test_base_mode_omits_shortest_and_tpad(self):
        filter_complex, video_label, audio_label = FFmpegVideoMixerAction._build_overlay_filter(
            self._one_placement(),
            VideoMixerOverlayAudioMode.BASE,
            VideoMixerOverlayDurationMode.BASE,
            base_pad_duration=None,
        )
        assert "tpad" not in filter_complex, "base mode must not pad the base video"
        assert "shortest=1" not in filter_complex
        assert video_label == "[vout]"
        assert audio_label == "0:a?"

    def test_shortest_mode_sets_shortest_flag_on_overlay(self):
        filter_complex, _, _ = FFmpegVideoMixerAction._build_overlay_filter(
            self._one_placement(),
            VideoMixerOverlayAudioMode.BASE,
            VideoMixerOverlayDurationMode.SHORTEST,
            base_pad_duration=None,
        )
        assert "shortest=1" in filter_complex
        assert "tpad" not in filter_complex

    def test_longest_mode_pads_base_and_amixes_longest(self):
        filter_complex, _, audio_label = FFmpegVideoMixerAction._build_overlay_filter(
            self._one_placement(),
            VideoMixerOverlayAudioMode.MIX,
            VideoMixerOverlayDurationMode.LONGEST,
            base_pad_duration=3.5,
        )
        # base is padded so overlay can keep compositing after base's original EOF
        assert "tpad=stop_mode=clone:stop_duration=3.5" in filter_complex
        # amix follows the same policy so audio doesn't cut early
        assert "amix" in filter_complex and "duration=longest" in filter_complex
        assert audio_label == "[aout]"

    def test_longest_mode_without_pad_skips_tpad(self):
        """When base already the longest, pad_duration=0 → tpad emitted with 0 makes no sense."""
        filter_complex, _, _ = FFmpegVideoMixerAction._build_overlay_filter(
            self._one_placement(),
            VideoMixerOverlayAudioMode.BASE,
            VideoMixerOverlayDurationMode.LONGEST,
            base_pad_duration=0.0,
        )
        assert "tpad" not in filter_complex, "no padding needed when base is already longest"


class TestDslNormalization:
    """These tests belong right next to the shape tests because normalization is
    what lets `_prepare_input` treat every combination uniformly. If DSL
    normalization regresses, the shape assumptions above collapse."""

    def test_overlay_str_is_wrapped_in_list(self):
        config = _adapter.validate_python({
            "method": "overlay",
            "video": "base.mp4",
            "overlay": "pip.mp4",
        })
        assert config.overlay == ["pip.mp4"]
        assert isinstance(config.placement, list) and len(config.placement) == 1

    def test_placement_dict_is_wrapped_in_list(self):
        config = _adapter.validate_python({
            "method": "overlay",
            "video": "base.mp4",
            "overlay": ["a.mp4", "b.mp4"],
            "placement": {"x": 30, "y": 40},
        })
        assert isinstance(config.placement, list)
        assert len(config.placement) == 1
        assert config.placement[0].x == 30

    def test_placement_str_is_wrapped_in_list(self):
        """Template references stay `str` at the schema layer — but still normalized to a list."""
        config = _adapter.validate_python({
            "method": "overlay",
            "video": "base.mp4",
            "overlay": ["a.mp4"],
            "placement": "${input.p}",
        })
        assert config.placement == ["${input.p}"]

    def test_default_placement_is_one_element_list(self):
        config = _adapter.validate_python({
            "method": "overlay",
            "video": "base.mp4",
            "overlay": ["a.mp4"],
        })
        assert isinstance(config.placement, list) and len(config.placement) == 1
        assert isinstance(config.placement[0], VideoOverlayPlacement)
