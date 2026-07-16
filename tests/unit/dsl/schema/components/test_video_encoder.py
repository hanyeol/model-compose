"""Tests for video-encoder component and action schemas."""

import pytest
from pydantic import TypeAdapter, ValidationError

from mindor.dsl.schema.action import VideoEncoderActionConfig
from mindor.dsl.schema.action.impl.media import (
    AudioEncoderConfig,
    VideoAudioEncodingConfig,
    VideoEncoderConfig,
)
from mindor.dsl.schema.component import VideoEncoderComponentConfig, VideoEncoderDriver

_video_encoder_adapter = TypeAdapter(VideoEncoderComponentConfig)


def _make_component(**values):
    """Validate a video-encoder component config through its discriminated union."""
    return _video_encoder_adapter.validate_python(values)


class TestVideoEncoderActionConfig:
    """Test VideoEncoderActionConfig schema validation."""

    def test_frames_only_config(self):
        """Frames input with frame_rate is valid."""
        config = VideoEncoderActionConfig(
            frames="${prev.frames}",
            frame_rate=30,
        )
        assert config.frames == "${prev.frames}"
        assert config.frame_rate == 30
        assert config.video is None
        assert config.audio is None
        assert config.streaming is False

    def test_video_only_config(self):
        """Existing video input without audio is valid."""
        config = VideoEncoderActionConfig(video="/tmp/in.mp4")
        assert config.video == "/tmp/in.mp4"
        assert config.frames is None
        assert config.frame_rate is None

    def test_video_with_audio_config(self):
        """Existing video + audio track is valid."""
        config = VideoEncoderActionConfig(
            video="/tmp/in.mp4",
            audio="/tmp/track.mp3",
        )
        assert config.video == "/tmp/in.mp4"
        assert config.audio == "/tmp/track.mp3"

    def test_frames_with_audio_config(self):
        """Frames + audio + encoding options is valid."""
        config = VideoEncoderActionConfig(
            frames="${prev.frames}",
            frame_rate=24,
            audio="${input.audio}",
            encoding=VideoAudioEncodingConfig(
                format="mp4",
                video=VideoEncoderConfig(codec="libx264", bitrate="2M"),
                audio=AudioEncoderConfig(codec="aac", bitrate="128k"),
            ),
        )
        assert config.frames == "${prev.frames}"
        assert config.frame_rate == 24
        assert config.encoding.format == "mp4"
        assert config.encoding.video.codec == "libx264"

    def test_streaming_flag(self):
        """streaming defaults to False and accepts bool/str."""
        assert VideoEncoderActionConfig(frames="${f}", frame_rate=30).streaming is False
        assert VideoEncoderActionConfig(frames="${f}", frame_rate=30, streaming=True).streaming is True
        assert VideoEncoderActionConfig(frames="${f}", frame_rate=30, streaming="${flag}").streaming == "${flag}"

    def test_missing_both_video_and_frames(self):
        """Config must have exactly one input source."""
        with pytest.raises(ValidationError) as exc_info:
            VideoEncoderActionConfig()
        assert "video" in str(exc_info.value).lower() or "frames" in str(exc_info.value).lower()

    def test_both_video_and_frames_rejected(self):
        """Providing both video and frames is invalid."""
        with pytest.raises(ValidationError):
            VideoEncoderActionConfig(video="/tmp/x.mp4", frames="${f}")

    def test_frame_rate_with_video_rejected(self):
        """frame_rate is only meaningful with frames input."""
        with pytest.raises(ValidationError) as exc_info:
            VideoEncoderActionConfig(video="/tmp/x.mp4", frame_rate=30)
        assert "frame_rate" in str(exc_info.value)

    def test_frame_rate_as_string_reference(self):
        """frame_rate accepts variable reference string."""
        config = VideoEncoderActionConfig(
            frames="${f}",
            frame_rate="${input.fps}",
        )
        assert config.frame_rate == "${input.fps}"

    def test_video_list_input(self):
        """video accepts a list of paths for batch encoding."""
        config = VideoEncoderActionConfig(video=["/tmp/a.mp4", "/tmp/b.mp4"])
        assert config.video == ["/tmp/a.mp4", "/tmp/b.mp4"]

    def test_batch_size_field(self):
        """batch_size accepts int or reference string."""
        assert VideoEncoderActionConfig(video="/tmp/x.mp4", batch_size=4).batch_size == 4
        assert VideoEncoderActionConfig(video="/tmp/x.mp4", batch_size="${n}").batch_size == "${n}"


class TestVideoEncoderComponentConfig:
    """Test VideoEncoderComponentConfig schema validation."""

    def test_minimal_valid_config(self):
        """Minimal valid component with explicit driver."""
        config = _make_component(
            id="encoder",
            type="video-encoder",
            driver="ffmpeg",
        )
        assert config.id == "encoder"
        assert config.type == "video-encoder"
        assert config.driver == VideoEncoderDriver.FFMPEG
        assert config.actions == []

    def test_component_with_frames_action(self):
        """Component with a frames-based action."""
        config = _make_component(
            id="encoder",
            type="video-encoder",
            driver="ffmpeg",
            actions=[
                {"frames": "${prev.frames}", "frame_rate": 30},
            ],
        )
        assert len(config.actions) == 1
        assert config.actions[0].frames == "${prev.frames}"

    def test_component_with_video_action(self):
        """Component with a video mux action."""
        config = _make_component(
            id="encoder",
            type="video-encoder",
            driver="ffmpeg",
            actions=[
                {"video": "${prev.video}", "audio": "${input.audio}"},
            ],
        )
        assert config.actions[0].video == "${prev.video}"
        assert config.actions[0].audio == "${input.audio}"

    def test_component_with_multiple_actions(self):
        """Component with multiple actions."""
        config = _make_component(
            id="encoder",
            type="video-encoder",
            driver="ffmpeg",
            actions=[
                {"id": "from_frames", "frames": "${f}", "frame_rate": 24},
                {"id": "mux", "video": "${v}", "audio": "${a}"},
            ],
        )
        assert len(config.actions) == 2
        assert config.actions[0].id == "from_frames"
        assert config.actions[1].id == "mux"


class TestVideoEncoderDriver:
    """Test the VideoEncoderDriver enum."""

    def test_ffmpeg_driver_value(self):
        assert VideoEncoderDriver.FFMPEG == "ffmpeg"

    def test_driver_enum_membership(self):
        assert "ffmpeg" in [d.value for d in VideoEncoderDriver]
