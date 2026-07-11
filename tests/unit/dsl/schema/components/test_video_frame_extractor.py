"""Tests for video-frame-extractor component and action schemas."""

import pytest
from pydantic import TypeAdapter, ValidationError

from mindor.dsl.schema.action import VideoFrameExtractorActionConfig
from mindor.dsl.schema.component import VideoFrameExtractorComponentConfig, VideoFrameExtractorDriver

_video_frame_extractor_adapter = TypeAdapter(VideoFrameExtractorComponentConfig)


def _make_component(**values):
    """Validate a video-frame-extractor component config through its discriminated union."""
    return _video_frame_extractor_adapter.validate_python(values)


class TestVideoFrameExtractorActionConfig:
    """Test VideoFrameExtractorActionConfig schema validation."""

    def test_minimal_valid_config(self):
        """Test minimal valid configuration with only required field."""
        config = VideoFrameExtractorActionConfig(
            video="/tmp/video.mp4"
        )
        assert config.video == "/tmp/video.mp4"
        assert config.frame_interval == 1
        assert config.start_time is None
        assert config.end_time is None
        assert config.max_frame_count is None

    def test_full_config(self):
        """Test full configuration with all fields."""
        config = VideoFrameExtractorActionConfig(
            video="${input.video}",
            frame_interval=2,
            start_time="00:00:10",
            end_time="00:01:00",
            max_frame_count=100
        )
        assert config.video == "${input.video}"
        assert config.frame_interval == 2
        assert config.start_time == "00:00:10"
        assert config.end_time == "00:01:00"
        assert config.max_frame_count == 100

    def test_missing_video(self):
        """Test that video is required."""
        with pytest.raises(ValidationError) as exc_info:
            VideoFrameExtractorActionConfig()
        assert "video" in str(exc_info.value).lower()

    def test_frame_interval_as_string(self):
        """Test that frame_interval accepts variable reference string."""
        config = VideoFrameExtractorActionConfig(
            video="/tmp/video.mp4",
            frame_interval="${input.interval}"
        )
        assert config.frame_interval == "${input.interval}"

    def test_max_frame_count_as_string(self):
        """Test that max_frame_count accepts variable reference string."""
        config = VideoFrameExtractorActionConfig(
            video="/tmp/video.mp4",
            max_frame_count="${input.limit}"
        )
        assert config.max_frame_count == "${input.limit}"

    def test_start_time_formats(self):
        """Test that start_time accepts various time formats."""
        for time_str in ["00:00:10", "10s", "1.5m", "0:30"]:
            config = VideoFrameExtractorActionConfig(
                video="/tmp/video.mp4",
                start_time=time_str
            )
            assert config.start_time == time_str

    def test_output_streaming_reference(self):
        """Test output field accepts streaming reference."""
        config = VideoFrameExtractorActionConfig(
            video="/tmp/video.mp4",
            output="${result[]}"
        )
        assert config.output == "${result[]}"

    def test_output_dict_reference(self):
        """Test output field accepts dict-style reference."""
        config = VideoFrameExtractorActionConfig(
            video="/tmp/video.mp4",
            output="${result.frames}"
        )
        assert config.output == "${result.frames}"


class TestVideoFrameExtractorComponentConfig:
    """Test VideoFrameExtractorComponentConfig schema validation."""

    def test_minimal_valid_config(self):
        """Test minimal valid component configuration."""
        config = _make_component(
            id="extractor",
            type="video-frame-extractor",
            driver="ffmpeg",
        )
        assert config.id == "extractor"
        assert config.type == "video-frame-extractor"
        assert config.driver == VideoFrameExtractorDriver.FFMPEG
        assert config.actions == []

    def test_explicit_opencv_driver(self):
        """Test explicit OpenCV driver."""
        config = _make_component(
            id="extractor",
            type="video-frame-extractor",
            driver="opencv",
        )
        assert config.driver == "opencv"

    def test_component_with_single_action(self):
        """Test component with a single action."""
        config = _make_component(
            id="extractor",
            type="video-frame-extractor",
            driver="ffmpeg",
            actions=[
                {"video": "${input.video}", "frame_interval": 2},
            ],
        )
        assert len(config.actions) == 1
        assert config.actions[0].video == "${input.video}"
        assert config.actions[0].frame_interval == 2

    def test_component_with_multiple_actions(self):
        """Test component with multiple actions."""
        config = _make_component(
            id="extractor",
            type="video-frame-extractor",
            driver="ffmpeg",
            actions=[
                {"id": "thumbnails", "video": "${input.video}", "max_frame_count": 10},
                {"id": "full", "video": "${input.video}", "frame_interval": 1},
            ],
        )
        assert len(config.actions) == 2
        assert config.actions[0].id == "thumbnails"
        assert config.actions[1].id == "full"


class TestVideoFrameExtractorDriver:
    """Test the VideoFrameExtractorDriver enum."""

    def test_opencv_driver_value(self):
        """Test that OPENCV driver has expected value."""
        assert VideoFrameExtractorDriver.OPENCV == "opencv"

    def test_driver_enum_membership(self):
        """Test driver enum members."""
        assert "opencv" in [d.value for d in VideoFrameExtractorDriver]
