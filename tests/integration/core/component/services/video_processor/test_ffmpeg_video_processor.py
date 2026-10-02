"""Tests for the FFmpeg video-processor driver's adjust-color method.

Verifies the composed filter chain so the ffmpeg invocation is driven with
the right arguments, without actually running ffmpeg on each test case.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest
from pydantic import TypeAdapter

from mindor.core.component.services.video_processor.drivers.ffmpeg import (
    FFmpegVideoProcessorAction,
)
from mindor.dsl.schema.action import VideoProcessorActionConfig


@pytest.fixture
def anyio_backend():
    return "asyncio"


class _CapturingAction(FFmpegVideoProcessorAction):
    """Intercepts `_run_ffmpeg_filter` to capture the composed filter string."""

    def __init__(self, config: VideoProcessorActionConfig):
        super().__init__(config)
        self.captured_video_filter: Optional[str] = None
        self.captured_audio_filter: Optional[str] = None

    async def _run_ffmpeg_filter(
        self,
        source: Any,
        video_filter: str,
        audio_filter: Optional[str],
        encoding: Any,
        cancellation_token: Any = None,
    ) -> Any:
        self.captured_video_filter = video_filter
        self.captured_audio_filter = audio_filter
        return None


def _config(**fields: Any) -> VideoProcessorActionConfig:
    return TypeAdapter(VideoProcessorActionConfig).validate_python({
        "method": "adjust-color",
        "video":  "${input.video}",
        **fields,
    })


class TestAdjustColorFilterChain:
    @pytest.mark.anyio
    async def test_brightness_uses_curves_filter(self):
        action = _CapturingAction(_config(brightness=0.5))
        await action._adjust_color(
            video=None, brightness=0.5, contrast=None, saturation=None, gamma=None, hue=None,
            encoding=None, cancellation_token=None,
        )
        assert action.captured_video_filter == "curves=all='0/0 1/0.5'"

    @pytest.mark.anyio
    async def test_contrast_saturation_gamma_merge_into_eq(self):
        action = _CapturingAction(_config(contrast=1.2, saturation=1.3, gamma=0.9))
        await action._adjust_color(
            video=None, brightness=None, contrast=1.2, saturation=1.3, gamma=0.9, hue=None,
            encoding=None, cancellation_token=None,
        )
        assert action.captured_video_filter == "eq=contrast=1.2:saturation=1.3:gamma=0.9"

    @pytest.mark.anyio
    async def test_hue_rotation_uses_hue_filter(self):
        action = _CapturingAction(_config(hue=120))
        await action._adjust_color(
            video=None, brightness=None, contrast=None, saturation=None, gamma=None, hue=120,
            encoding=None, cancellation_token=None,
        )
        assert action.captured_video_filter == "hue=h=120"

    @pytest.mark.anyio
    async def test_full_chain_orders_curves_then_eq_then_hue(self):
        action = _CapturingAction(_config(brightness=0.9, contrast=1.1, saturation=1.2, gamma=1.0, hue=30))
        await action._adjust_color(
            video=None, brightness=0.9, contrast=1.1, saturation=1.2, gamma=1.0, hue=30,
            encoding=None, cancellation_token=None,
        )
        assert action.captured_video_filter == (
            "curves=all='0/0 1/0.9',"
            "eq=contrast=1.1:saturation=1.2:gamma=1.0,"
            "hue=h=30"
        )
        # Audio is left untouched.
        assert action.captured_audio_filter is None

    def test_schema_rejects_empty_adjust_color(self):
        with pytest.raises(Exception, match="at least one"):
            TypeAdapter(VideoProcessorActionConfig).validate_python({
                "method": "adjust-color", "video": "${input.video}",
            })


class TestSingleEffectAdjustFilters:
    """Single-effect adjust-* methods mirror image-processor's shortcuts."""

    @pytest.mark.anyio
    async def test_adjust_brightness(self):
        action = _CapturingAction(TypeAdapter(VideoProcessorActionConfig).validate_python({
            "method": "adjust-brightness", "video": "${input.video}", "factor": 0.5,
        }))
        await action._adjust_brightness(None, 0.5, None, None)
        assert action.captured_video_filter == "curves=all='0/0 1/0.5'"

    @pytest.mark.anyio
    async def test_adjust_contrast(self):
        action = _CapturingAction(TypeAdapter(VideoProcessorActionConfig).validate_python({
            "method": "adjust-contrast", "video": "${input.video}", "factor": 1.5,
        }))
        await action._adjust_contrast(None, 1.5, None, None)
        assert action.captured_video_filter == "eq=contrast=1.5"

    @pytest.mark.anyio
    async def test_adjust_saturation(self):
        action = _CapturingAction(TypeAdapter(VideoProcessorActionConfig).validate_python({
            "method": "adjust-saturation", "video": "${input.video}", "factor": 1.3,
        }))
        await action._adjust_saturation(None, 1.3, None, None)
        assert action.captured_video_filter == "eq=saturation=1.3"

    @pytest.mark.anyio
    async def test_adjust_gamma(self):
        action = _CapturingAction(TypeAdapter(VideoProcessorActionConfig).validate_python({
            "method": "adjust-gamma", "video": "${input.video}", "gamma": 2.0,
        }))
        await action._adjust_gamma(None, 2.0, None, None)
        assert action.captured_video_filter == "eq=gamma=2.0"

    @pytest.mark.anyio
    async def test_adjust_hue(self):
        action = _CapturingAction(TypeAdapter(VideoProcessorActionConfig).validate_python({
            "method": "adjust-hue", "video": "${input.video}", "hue": 90,
        }))
        await action._adjust_hue(None, 90, None, None)
        assert action.captured_video_filter == "hue=h=90"
