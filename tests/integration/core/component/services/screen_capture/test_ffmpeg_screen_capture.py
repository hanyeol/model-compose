"""Tests for the FFmpeg screen-capture driver.

Two layers, matching the audio_converter test structure:
  - Argv/config layer: verifies ffmpeg (and audiotee) command construction, the
    format/codec/muxer resolvers, and dispatch through _capture(). Runs
    everywhere; hardware not required (subprocess calls are patched).
  - Runtime layer: spawns real ffmpeg against the local display / microphone.
    Skipped unless the environment opts in with SCREEN_CAPTURE_LIVE=1 so CI /
    headless runs stay clean.
"""

from __future__ import annotations

import asyncio
import os
import platform
import shutil
import subprocess
import time
from typing import Any, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.screen_capture.drivers.common import (
    AudioEncoderParams,
    VideoAudioEncodingParams,
    VideoEncoderParams,
)
from mindor.core.component.services.screen_capture.drivers.ffmpeg import (
    FFmpegScreenCaptureAction,
)
from mindor.core.foundation.streaming.audio import AudioStreamResource
from mindor.core.foundation.streaming.video import VideoStreamResource
from mindor.dsl.schema.action import (
    ScreenCaptureActionConfig,
    ScreenCaptureActionMethod,
    ScreenCaptureAudioSource,
    ScreenCaptureRegion,
    ScreenCaptureVideoSource,
)
from mindor.dsl.schema.action.impl.media import (
    AudioEncoderConfig,
    VideoAudioEncodingConfig,
    VideoEncoderConfig,
)


ffmpeg_required = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg not available on PATH"
)

# Runtime tests spawn real ffmpeg against the local display/audio devices, so
# they only run when the developer opts in. `pytest -m runtime` still filters
# them; the env gate is what keeps CI green.
live_only = pytest.mark.skipif(
    os.environ.get("SCREEN_CAPTURE_LIVE") != "1",
    reason="set SCREEN_CAPTURE_LIVE=1 to run tests that access the real display/audio",
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _make_config(**kwargs: Any) -> ScreenCaptureActionConfig:
    defaults = dict(
        method=ScreenCaptureActionMethod.CAPTURE,
        video_source=ScreenCaptureVideoSource.DISPLAY,
        display=0,
        include_video=True,
        include_audio=False,
        audio_source=ScreenCaptureAudioSource.NONE,
        framerate=30,
        duration=None,
    )
    defaults.update(kwargs)
    return ScreenCaptureActionConfig(**defaults)


def _make_context() -> ComponentActionContext:
    """Mock context that echoes render_variable and records register_source.

    screen-capture has no input side (no render_video / render_audio), so this
    is much thinner than the audio_converter fixture.
    """
    ctx = MagicMock(spec=ComponentActionContext)
    sources: dict = {}

    def register_source(key: str, value: Any, scope: Any = None) -> None:
        sources[key] = value

    async def render_variable(value, **kwargs):
        return value

    ctx.register_source = MagicMock(side_effect=register_source)
    ctx.render_variable = AsyncMock(side_effect=render_variable)
    ctx._sources = sources  # exposed for tests that want to inspect
    return ctx


class _RecordingProcess:
    """Stand-in for asyncio.subprocess.Process that emits a canned byte stream.

    Only implements what the driver actually touches: `stdout.read()` (draining
    encoded chunks) and `kill()` / `wait()` (cleanup on generator close).
    """

    def __init__(self, chunks: List[bytes]):
        self._chunks = list(chunks)
        self.returncode = None
        self.killed = False
        self.stdout = MagicMock()

        async def _read(_size: int) -> bytes:
            if self._chunks:
                return self._chunks.pop(0)
            self.returncode = 0
            return b""

        self.stdout.read = AsyncMock(side_effect=_read)

    def kill(self) -> None:
        self.killed = True
        if self.returncode is None:
            self.returncode = -9

    async def wait(self) -> int:
        return self.returncode if self.returncode is not None else 0


# ---------------------------------------------------------------------------
# Argv construction — the sharp edge where OS branching lives.
# ---------------------------------------------------------------------------


class TestVideoInputArgs:
    """OS-specific ffmpeg input flags for the video track."""

    def test_darwin_avfoundation(self):
        action = FFmpegScreenCaptureAction(_make_config())
        argv = action._build_video_input_args("Darwin", display=2, framerate=15)
        assert argv[:2] == ["-f", "avfoundation"]
        assert "-framerate" in argv and "15" in argv
        # display is passed as "<n>:none" to avoid picking up an audio device.
        assert "2:none" in argv

    def test_windows_gdigrab(self):
        action = FFmpegScreenCaptureAction(_make_config())
        argv = action._build_video_input_args("Windows", display=0, framerate=30)
        assert argv[:2] == ["-f", "gdigrab"]
        assert "desktop" in argv

    def test_linux_x11grab_uses_display_env(self, monkeypatch):
        monkeypatch.setenv("DISPLAY", ":1")
        action = FFmpegScreenCaptureAction(_make_config())
        argv = action._build_video_input_args("Linux", display=0, framerate=30)
        assert argv[:2] == ["-f", "x11grab"]
        assert ":1" in argv

    def test_linux_x11grab_default_display(self, monkeypatch):
        monkeypatch.delenv("DISPLAY", raising=False)
        action = FFmpegScreenCaptureAction(_make_config())
        argv = action._build_video_input_args("Linux", display=0, framerate=30)
        assert ":0.0" in argv

    def test_unsupported_platform_raises(self):
        action = FFmpegScreenCaptureAction(_make_config())
        with pytest.raises(NotImplementedError, match="platform"):
            action._build_video_input_args("Plan9", display=0, framerate=30)


class TestVideoInputArgsWithRegion:
    """Region flags land at input time on Windows/Linux and post-decode on macOS."""

    _REGION = { "x": 100, "y": 50, "width": 640, "height": 360 }

    def test_darwin_region_stays_at_input_unchanged(self):
        # avfoundation can't crop at input; the region is applied via the
        # -vf crop filter in _start_video_capture, not here.
        action = FFmpegScreenCaptureAction(_make_config())
        argv = action._build_video_input_args("Darwin", display=0, framerate=30, region=self._REGION)
        assert "-video_size" not in argv
        assert "-offset_x" not in argv

    def test_windows_region_uses_offset_and_video_size(self):
        action = FFmpegScreenCaptureAction(_make_config())
        argv = action._build_video_input_args("Windows", display=0, framerate=30, region=self._REGION)
        assert "-offset_x" in argv and "100" in argv
        assert "-offset_y" in argv and "50" in argv
        assert "-video_size" in argv and "640x360" in argv
        assert "desktop" in argv

    def test_linux_region_baked_into_display_spec(self, monkeypatch):
        monkeypatch.setenv("DISPLAY", ":0")
        action = FFmpegScreenCaptureAction(_make_config())
        argv = action._build_video_input_args("Linux", display=0, framerate=30, region=self._REGION)
        # x11grab reads the offset from the display spec.
        assert ":0+100,50" in argv
        assert "-video_size" in argv and "640x360" in argv


class TestAudioInputArgs:
    """OS + audio_source matrix for the audio track (excluding macOS system loopback,
    which is served by the audiotee sidecar path — see TestMacosSystemAudio)."""

    def test_darwin_microphone(self):
        action = FFmpegScreenCaptureAction(_make_config())
        argv = action._build_audio_input_args("Darwin", ScreenCaptureAudioSource.MICROPHONE)
        assert argv == ["-f", "avfoundation", "-i", ":default"]

    def test_linux_system_uses_pulse_monitor(self):
        action = FFmpegScreenCaptureAction(_make_config())
        argv = action._build_audio_input_args("Linux", ScreenCaptureAudioSource.SYSTEM)
        assert argv[:2] == ["-f", "pulse"]
        # The monitor source is the whole point of the Linux system path.
        assert "default.monitor" in argv

    def test_linux_microphone(self):
        action = FFmpegScreenCaptureAction(_make_config())
        argv = action._build_audio_input_args("Linux", ScreenCaptureAudioSource.MICROPHONE)
        assert argv == ["-f", "pulse", "-i", "default"]

    def test_windows_system_wasapi_loopback(self):
        action = FFmpegScreenCaptureAction(_make_config())
        argv = action._build_audio_input_args("Windows", ScreenCaptureAudioSource.SYSTEM)
        assert argv[:2] == ["-f", "dshow"]

    def test_windows_microphone(self):
        action = FFmpegScreenCaptureAction(_make_config())
        argv = action._build_audio_input_args("Windows", ScreenCaptureAudioSource.MICROPHONE)
        assert argv[:2] == ["-f", "dshow"]

    def test_unsupported_combination_raises(self):
        action = FFmpegScreenCaptureAction(_make_config())
        with pytest.raises(NotImplementedError, match="Audio source"):
            action._build_audio_input_args("Plan9", ScreenCaptureAudioSource.MICROPHONE)


class TestFormatResolvers:
    """Container / codec / muxer resolution — pure logic, easy to break silently."""

    def test_default_video_format_is_streaming_container(self):
        action = FFmpegScreenCaptureAction(_make_config())
        assert action._resolve_container_format(None) == "ts"

    def test_video_format_lowercased(self):
        action = FFmpegScreenCaptureAction(_make_config())
        encoding = VideoAudioEncodingParams(format="MP4")
        assert action._resolve_container_format(encoding) == "mp4"

    def test_default_video_codec(self):
        action = FFmpegScreenCaptureAction(_make_config())
        assert action._resolve_video_codec(None) == "libx264"

    def test_video_codec_override(self):
        action = FFmpegScreenCaptureAction(_make_config())
        encoding = VideoAudioEncodingParams(video=VideoEncoderParams(codec="libvpx-vp9"))
        assert action._resolve_video_codec(encoding) == "libvpx-vp9"

    def test_container_muxer_maps_ts_to_mpegts(self):
        # "ts" is the content-type shorthand; ffmpeg's muxer is "mpegts".
        assert FFmpegScreenCaptureAction._container_muxer("ts") == "mpegts"
        assert FFmpegScreenCaptureAction._container_muxer("mp4") == "mp4"

    @pytest.mark.parametrize(
        "format,expected",
        [
            ("aac", "aac"),
            ("wav", "wav"),
            ("flac", "flac"),
            ("mp3", "mp3"),
            ("m4a", "m4a"),
            ("ogg", "ogg"),
            ("opus", "opus"),
        ],
    )
    def test_audio_only_containers_pass_through(self, format, expected):
        action = FFmpegScreenCaptureAction(_make_config())
        encoding = VideoAudioEncodingParams(format=format)
        assert action._resolve_audio_format(encoding) == expected

    @pytest.mark.parametrize(
        "format,expected",
        [
            ("mp4", "m4a"),
            ("mov", "m4a"),
            ("webm", "ogg"),
        ],
    )
    def test_video_containers_map_to_matching_audio_container(self, format, expected):
        action = FFmpegScreenCaptureAction(_make_config())
        encoding = VideoAudioEncodingParams(format=format)
        assert action._resolve_audio_format(encoding) == expected

    def test_default_audio_format(self):
        action = FFmpegScreenCaptureAction(_make_config())
        assert action._resolve_audio_format(None) == "aac"

    def test_audio_codec_defaults_to_libopus_for_ogg(self):
        # Emitting an ogg container with aac inside would be invalid; the
        # resolver has to know to pick opus.
        action = FFmpegScreenCaptureAction(_make_config())
        assert action._resolve_audio_codec(None, "ogg") == "libopus"
        assert action._resolve_audio_codec(None, "aac") == "aac"

    def test_audio_codec_explicit_override_wins(self):
        action = FFmpegScreenCaptureAction(_make_config())
        encoding = VideoAudioEncodingParams(audio=AudioEncoderParams(codec="flac"))
        assert action._resolve_audio_codec(encoding, "wav") == "flac"

    def test_audio_muxer_maps_aac_to_adts(self):
        # Raw AAC needs an ADTS wrapper for pipe:1 to be decodable.
        assert FFmpegScreenCaptureAction._audio_muxer("aac") == "adts"

    def test_audio_muxer_maps_m4a_to_ipod(self):
        # m4a (audio-only mp4) uses the "ipod" muxer for pipe output.
        assert FFmpegScreenCaptureAction._audio_muxer("m4a") == "ipod"

    def test_audio_muxer_passthrough(self):
        assert FFmpegScreenCaptureAction._audio_muxer("wav") == "wav"
        assert FFmpegScreenCaptureAction._audio_muxer("flac") == "flac"


# ---------------------------------------------------------------------------
# Dispatch tests — hardware-free, using a fake subprocess.
# ---------------------------------------------------------------------------


def _patch_subprocess(monkeypatch, canned_chunks: List[bytes]) -> List[List[str]]:
    """Replace asyncio.create_subprocess_exec so it returns _RecordingProcess.

    Returns the list of argvs seen, so tests can assert on what would have been
    executed without actually spawning ffmpeg.
    """
    seen: List[List[str]] = []

    async def _fake_exec(*args, **kwargs):
        seen.append(list(args))
        return _RecordingProcess(canned_chunks)

    monkeypatch.setattr(
        "mindor.core.component.services.screen_capture.drivers.ffmpeg.asyncio.create_subprocess_exec",
        _fake_exec,
    )
    return seen


@pytest.mark.anyio
async def test_video_only_returns_video_stream_resource(monkeypatch):
    """_capture() shape: video-only → VideoStreamResource with capture_pts attrs."""
    seen = _patch_subprocess(monkeypatch, [b"\x00\x01\x02\x03"])
    monkeypatch.setattr(
        "mindor.core.component.services.screen_capture.drivers.ffmpeg.platform.system",
        lambda: "Linux",
    )
    monkeypatch.setenv("DISPLAY", ":0")

    action = FFmpegScreenCaptureAction(_make_config(include_video=True, include_audio=False))
    result = await action.run(_make_context())

    assert set(result.keys()) == {"video", "audio", "capture_pts"}
    assert isinstance(result["video"], VideoStreamResource)
    assert result["audio"] is None
    assert isinstance(result["capture_pts"], float)
    assert result["video"].attrs.get("capture_pts") == result["capture_pts"]
    assert result["video"].format == "ts"
    assert result["video"].content_type == "video/mp2t"

    # Only one ffmpeg was spawned (the video one).
    assert len(seen) == 1
    assert seen[0][0] == "ffmpeg"
    assert seen[0][1:5] == ["-hide_banner", "-nostats", "-loglevel", "warning"]

    # Draining consumes the canned chunks and closes cleanly.
    chunks = []
    async for chunk in result["video"]:
        chunks.append(chunk)
    assert chunks == [b"\x00\x01\x02\x03"]
    await result["video"].close()


@pytest.mark.anyio
async def test_audio_only_returns_audio_stream_resource(monkeypatch):
    seen = _patch_subprocess(monkeypatch, [b"\xaa\xbb"])
    monkeypatch.setattr(
        "mindor.core.component.services.screen_capture.drivers.ffmpeg.platform.system",
        lambda: "Linux",
    )

    action = FFmpegScreenCaptureAction(
        _make_config(
            include_video=False,
            include_audio=True,
            audio_source=ScreenCaptureAudioSource.SYSTEM,
        )
    )
    result = await action.run(_make_context())

    assert result["video"] is None
    assert isinstance(result["audio"], AudioStreamResource)
    assert result["audio"].format == "aac"
    assert result["audio"].content_type == "audio/aac"
    assert result["audio"].attrs.get("capture_pts") == result["capture_pts"]

    assert len(seen) == 1
    argv = seen[0]
    # Linux system audio must reach the PulseAudio monitor source.
    assert "pulse" in argv
    assert "default.monitor" in argv

    async for _ in result["audio"]:
        pass
    await result["audio"].close()


@pytest.mark.anyio
async def test_video_plus_audio_spawns_two_processes(monkeypatch):
    seen = _patch_subprocess(monkeypatch, [b"x"])
    monkeypatch.setattr(
        "mindor.core.component.services.screen_capture.drivers.ffmpeg.platform.system",
        lambda: "Linux",
    )

    action = FFmpegScreenCaptureAction(
        _make_config(
            include_video=True,
            include_audio=True,
            audio_source=ScreenCaptureAudioSource.MICROPHONE,
        )
    )
    result = await action.run(_make_context())

    assert isinstance(result["video"], VideoStreamResource)
    assert isinstance(result["audio"], AudioStreamResource)
    # Both tracks share the same capture_pts anchor so downstream A/V sync works.
    assert result["video"].attrs["capture_pts"] == result["audio"].attrs["capture_pts"]

    # Two ffmpeg spawns: one per track.
    assert len(seen) == 2
    async for _ in result["video"]:
        pass
    async for _ in result["audio"]:
        pass
    await result["video"].close()
    await result["audio"].close()


@pytest.mark.anyio
async def test_duration_appends_t_flag_to_ffmpeg(monkeypatch):
    seen = _patch_subprocess(monkeypatch, [b"x"])
    monkeypatch.setattr(
        "mindor.core.component.services.screen_capture.drivers.ffmpeg.platform.system",
        lambda: "Linux",
    )

    action = FFmpegScreenCaptureAction(
        _make_config(include_video=True, include_audio=False, duration=5)
    )
    result = await action.run(_make_context())

    assert len(seen) == 1
    argv = seen[0]
    assert "-t" in argv
    assert "5.0" in argv

    async for _ in result["video"]:
        pass
    await result["video"].close()


@pytest.mark.anyio
async def test_infinite_duration_omits_t_flag(monkeypatch):
    seen = _patch_subprocess(monkeypatch, [b"x"])
    monkeypatch.setattr(
        "mindor.core.component.services.screen_capture.drivers.ffmpeg.platform.system",
        lambda: "Linux",
    )

    action = FFmpegScreenCaptureAction(
        _make_config(include_video=True, include_audio=False, duration=None)
    )
    result = await action.run(_make_context())

    assert "-t" not in seen[0]
    async for _ in result["video"]:
        pass
    await result["video"].close()


@pytest.mark.anyio
async def test_mp4_container_gets_fragmentation_flags(monkeypatch):
    """Fragmented-mp4 movflags are required for pipe output; mpegts doesn't need them."""
    seen = _patch_subprocess(monkeypatch, [b"x"])
    monkeypatch.setattr(
        "mindor.core.component.services.screen_capture.drivers.ffmpeg.platform.system",
        lambda: "Linux",
    )

    action = FFmpegScreenCaptureAction(
        _make_config(
            include_video=True,
            include_audio=False,
            encoding=VideoAudioEncodingConfig(format="mp4"),
        )
    )
    result = await action.run(_make_context())

    argv = seen[0]
    assert "-movflags" in argv
    idx = argv.index("-movflags")
    assert "frag_keyframe" in argv[idx + 1]

    async for _ in result["video"]:
        pass
    await result["video"].close()


@pytest.mark.anyio
async def test_mpegts_container_does_not_add_movflags(monkeypatch):
    seen = _patch_subprocess(monkeypatch, [b"x"])
    monkeypatch.setattr(
        "mindor.core.component.services.screen_capture.drivers.ffmpeg.platform.system",
        lambda: "Linux",
    )

    action = FFmpegScreenCaptureAction(_make_config(include_video=True, include_audio=False))
    result = await action.run(_make_context())

    assert "-movflags" not in seen[0]
    async for _ in result["video"]:
        pass
    await result["video"].close()


@pytest.mark.anyio
async def test_unsupported_video_source_raises_not_implemented():
    # display + region are wired; window is deferred and must still raise clearly.
    class _WindowSource:
        value = "window"

    action = FFmpegScreenCaptureAction(_make_config(include_video=True))
    with pytest.raises(NotImplementedError, match="video_source 'window'"):
        await action._start_video_capture(
            "Linux",
            {
                "video_source": _WindowSource(),
                "encoding": None,
                "framerate": 30,
                "display": 0,
                "region": None,
                "duration": None,
            },
        )


class TestRegionDispatch:
    """End-to-end wiring from config → argv for the region path."""

    _REGION = ScreenCaptureRegion(x=10, y=20, width=320, height=240)

    @pytest.mark.anyio
    async def test_region_missing_when_video_source_is_region_raises(self):
        # The pydantic validator catches this at config load time so the
        # driver never even runs; make sure that guarantee holds.
        with pytest.raises(ValueError, match="'region' must be provided"):
            _make_config(
                video_source=ScreenCaptureVideoSource.REGION,
                region=None,
            )

    @pytest.mark.anyio
    async def test_linux_region_reaches_ffmpeg_argv(self, monkeypatch):
        seen = _patch_subprocess(monkeypatch, [b"x"])
        monkeypatch.setattr(
            "mindor.core.component.services.screen_capture.drivers.ffmpeg.platform.system",
            lambda: "Linux",
        )
        monkeypatch.setenv("DISPLAY", ":0")

        action = FFmpegScreenCaptureAction(
            _make_config(
                video_source=ScreenCaptureVideoSource.REGION,
                region=self._REGION,
                include_video=True,
                include_audio=False,
            )
        )
        result = await action.run(_make_context())

        argv = seen[0]
        assert ":0+10,20" in argv
        assert "320x240" in argv
        # Linux does not need a -vf crop filter for region capture.
        assert "-vf" not in argv or "crop=" not in " ".join(argv)

        async for _ in result["video"]:
            pass
        await result["video"].close()

    @pytest.mark.anyio
    async def test_darwin_region_adds_crop_filter(self, monkeypatch):
        seen = _patch_subprocess(monkeypatch, [b"x"])
        monkeypatch.setattr(
            "mindor.core.component.services.screen_capture.drivers.ffmpeg.platform.system",
            lambda: "Darwin",
        )
        action = FFmpegScreenCaptureAction(
            _make_config(
                video_source=ScreenCaptureVideoSource.REGION,
                region=self._REGION,
                include_video=True,
                include_audio=False,
            )
        )
        result = await action.run(_make_context())

        argv = seen[0]
        # avfoundation input flags unchanged.
        assert "avfoundation" in argv
        # crop filter reflects the region.
        assert "-vf" in argv
        assert "crop=320:240:10:20" in argv

        async for _ in result["video"]:
            pass
        await result["video"].close()

    @pytest.mark.anyio
    async def test_windows_region_uses_input_offset(self, monkeypatch):
        seen = _patch_subprocess(monkeypatch, [b"x"])
        monkeypatch.setattr(
            "mindor.core.component.services.screen_capture.drivers.ffmpeg.platform.system",
            lambda: "Windows",
        )
        action = FFmpegScreenCaptureAction(
            _make_config(
                video_source=ScreenCaptureVideoSource.REGION,
                region=self._REGION,
                include_video=True,
                include_audio=False,
            )
        )
        result = await action.run(_make_context())

        argv = seen[0]
        assert "-offset_x" in argv and "10" in argv
        assert "-offset_y" in argv and "20" in argv
        assert "-video_size" in argv and "320x240" in argv

        async for _ in result["video"]:
            pass
        await result["video"].close()

    @pytest.mark.anyio
    async def test_region_dimensions_must_be_positive(self, monkeypatch):
        monkeypatch.setattr(
            "mindor.core.component.services.screen_capture.drivers.ffmpeg.platform.system",
            lambda: "Linux",
        )
        action = FFmpegScreenCaptureAction(
            _make_config(
                video_source=ScreenCaptureVideoSource.REGION,
                region=ScreenCaptureRegion(x=0, y=0, width=0, height=100),
                include_video=True,
                include_audio=False,
            )
        )
        with pytest.raises(ValueError, match="region size"):
            await action.run(_make_context())

    @pytest.mark.anyio
    async def test_region_origin_must_be_non_negative(self, monkeypatch):
        monkeypatch.setattr(
            "mindor.core.component.services.screen_capture.drivers.ffmpeg.platform.system",
            lambda: "Linux",
        )
        action = FFmpegScreenCaptureAction(
            _make_config(
                video_source=ScreenCaptureVideoSource.REGION,
                region=ScreenCaptureRegion(x=-5, y=0, width=100, height=100),
                include_video=True,
                include_audio=False,
            )
        )
        with pytest.raises(ValueError, match="region origin"):
            await action.run(_make_context())

    @pytest.mark.anyio
    async def test_region_string_video_source_still_requires_region_param(self, monkeypatch):
        # When video_source is an unresolved variable expression (e.g.
        # "${input.video_source}"), pydantic keeps it as a raw string and the
        # schema's region-required validator can't see it. Once render_variable
        # returns "region" at runtime, the driver's own check has to catch the
        # missing region.
        monkeypatch.setattr(
            "mindor.core.component.services.screen_capture.drivers.ffmpeg.platform.system",
            lambda: "Linux",
        )
        config = _make_config(
            video_source="${input.video_source}",
            region=None,
            include_video=True,
            include_audio=False,
        )
        # Sanity check: pydantic did keep it as a string.
        assert isinstance(config.video_source, str)

        ctx = _make_context()

        async def render_variable(value, **kwargs):
            if value == "${input.video_source}":
                return "region"
            return value

        ctx.render_variable = AsyncMock(side_effect=render_variable)

        action = FFmpegScreenCaptureAction(config)
        with pytest.raises(ValueError, match="'region' must be provided"):
            await action.run(ctx)


@pytest.mark.anyio
async def test_output_template_overrides_return_value(monkeypatch):
    """Consistency with other components: `output` template on the action
    overrides the raw dict result while `result` is still registered."""
    _patch_subprocess(monkeypatch, [b"x"])
    monkeypatch.setattr(
        "mindor.core.component.services.screen_capture.drivers.ffmpeg.platform.system",
        lambda: "Linux",
    )

    ctx = _make_context()
    # Rig render_variable so ${result.capture_pts} pulls from the registered dict.
    async def render_variable(value, **kwargs):
        if value == "${result.capture_pts}":
            return ctx._sources["result"]["capture_pts"]
        return value

    ctx.render_variable = AsyncMock(side_effect=render_variable)

    action = FFmpegScreenCaptureAction(
        _make_config(include_video=True, include_audio=False, output="${result.capture_pts}")
    )
    result = await action.run(ctx)

    assert isinstance(result, float)
    # `result` source still registered as the full dict.
    registered_keys = [c.args[0] for c in ctx.register_source.call_args_list]
    assert "result" in registered_keys


class TestEncodingRendering:
    """encoding.* fields go through render_variable, so ${input.foo} references
    inside VideoAudioEncodingConfig are resolved at runtime instead of being
    passed to ffmpeg as literal '${...}' strings."""

    @pytest.mark.anyio
    async def test_encoding_format_reference_is_rendered_into_argv(self, monkeypatch):
        seen = _patch_subprocess(monkeypatch, [b"x"])
        monkeypatch.setattr(
            "mindor.core.component.services.screen_capture.drivers.ffmpeg.platform.system",
            lambda: "Linux",
        )
        ctx = _make_context()

        async def render_variable(value, **kwargs):
            if value == "${input.format}":
                return "webm"
            return value

        ctx.render_variable = AsyncMock(side_effect=render_variable)

        action = FFmpegScreenCaptureAction(
            _make_config(
                include_video=True,
                include_audio=False,
                encoding=VideoAudioEncodingConfig(format="${input.format}"),
            )
        )
        result = await action.run(ctx)

        # The rendered container ("webm") ends up in ffmpeg -f, not the literal.
        argv = seen[0]
        assert "webm" in argv
        assert "${input.format}" not in argv

        async for _ in result["video"]:
            pass
        await result["video"].close()

    @pytest.mark.anyio
    async def test_encoding_video_bitrate_reference_is_parsed_and_rendered(self, monkeypatch):
        seen = _patch_subprocess(monkeypatch, [b"x"])
        monkeypatch.setattr(
            "mindor.core.component.services.screen_capture.drivers.ffmpeg.platform.system",
            lambda: "Linux",
        )
        ctx = _make_context()

        async def render_variable(value, **kwargs):
            if value == "${input.bitrate}":
                return "6M"
            return value

        ctx.render_variable = AsyncMock(side_effect=render_variable)

        action = FFmpegScreenCaptureAction(
            _make_config(
                include_video=True,
                include_audio=False,
                encoding=VideoAudioEncodingConfig(
                    video=VideoEncoderConfig(bitrate="${input.bitrate}"),
                ),
            )
        )
        result = await action.run(ctx)

        # parse_bitrate converts "6M" → 6_000_000; that int should be what
        # gets stringified for the -b:v flag.
        argv = seen[0]
        assert "-b:v" in argv
        idx = argv.index("-b:v")
        assert argv[idx + 1] == str(6_000_000)

        async for _ in result["video"]:
            pass
        await result["video"].close()


class TestSourceInterpolation:
    """`video_source` / `audio_source` accept both enums and interpolated strings
    (e.g. `${input.audio_source}`), so the driver has to normalize either form."""

    @pytest.mark.anyio
    async def test_string_video_source_is_accepted(self, monkeypatch):
        _patch_subprocess(monkeypatch, [b"x"])
        monkeypatch.setattr(
            "mindor.core.component.services.screen_capture.drivers.ffmpeg.platform.system",
            lambda: "Linux",
        )
        # Pass a raw string in place of the enum; pydantic keeps it as-is because
        # the field is Union[enum, str].
        action = FFmpegScreenCaptureAction(
            _make_config(video_source="display", include_video=True, include_audio=False)
        )
        result = await action.run(_make_context())
        assert isinstance(result["video"], VideoStreamResource)
        async for _ in result["video"]:
            pass
        await result["video"].close()

    @pytest.mark.anyio
    async def test_string_audio_source_is_accepted(self, monkeypatch):
        seen = _patch_subprocess(monkeypatch, [b"x"])
        monkeypatch.setattr(
            "mindor.core.component.services.screen_capture.drivers.ffmpeg.platform.system",
            lambda: "Linux",
        )
        action = FFmpegScreenCaptureAction(
            _make_config(
                include_video=False,
                include_audio=True,
                audio_source="microphone",
            )
        )
        result = await action.run(_make_context())
        # Linux microphone path resolves to pulse -i default.
        assert "pulse" in seen[0]
        assert "default" in seen[0]
        async for _ in result["audio"]:
            pass
        await result["audio"].close()

    @pytest.mark.anyio
    async def test_unknown_video_source_string_raises(self, monkeypatch):
        monkeypatch.setattr(
            "mindor.core.component.services.screen_capture.drivers.ffmpeg.platform.system",
            lambda: "Linux",
        )
        action = FFmpegScreenCaptureAction(
            _make_config(video_source="hologram", include_video=True, include_audio=False)
        )
        with pytest.raises(ValueError, match="video_source"):
            await action.run(_make_context())

    @pytest.mark.anyio
    async def test_unknown_audio_source_string_raises(self, monkeypatch):
        monkeypatch.setattr(
            "mindor.core.component.services.screen_capture.drivers.ffmpeg.platform.system",
            lambda: "Linux",
        )
        action = FFmpegScreenCaptureAction(
            _make_config(
                include_video=False,
                include_audio=True,
                audio_source="hologram",
            )
        )
        with pytest.raises(ValueError, match="audio_source"):
            await action.run(_make_context())


class TestMacosSystemAudio:
    """The audiotee sidecar path is macOS-only and lives outside the ffmpeg-only
    dispatch, so it needs its own dispatch check."""

    @pytest.mark.anyio
    async def test_missing_audiotee_raises_with_actionable_message(self, monkeypatch):
        monkeypatch.setattr(
            "mindor.core.component.services.screen_capture.drivers.ffmpeg.platform.system",
            lambda: "Darwin",
        )
        monkeypatch.setattr(
            "mindor.core.component.services.screen_capture.drivers.ffmpeg.shutil.which",
            lambda name: None,
        )
        action = FFmpegScreenCaptureAction(
            _make_config(
                include_video=False,
                include_audio=True,
                audio_source=ScreenCaptureAudioSource.SYSTEM,
            )
        )
        with pytest.raises(RuntimeError, match="audiotee"):
            await action.run(_make_context())

    @pytest.mark.anyio
    async def test_darwin_system_audio_spawns_audiotee_and_ffmpeg(self, monkeypatch):
        seen = _patch_subprocess(monkeypatch, [b"pcm-chunk"])
        monkeypatch.setattr(
            "mindor.core.component.services.screen_capture.drivers.ffmpeg.platform.system",
            lambda: "Darwin",
        )
        monkeypatch.setattr(
            "mindor.core.component.services.screen_capture.drivers.ffmpeg.shutil.which",
            lambda name: "/fake/audiotee" if name == "audiotee" else None,
        )

        action = FFmpegScreenCaptureAction(
            _make_config(
                include_video=False,
                include_audio=True,
                audio_source=ScreenCaptureAudioSource.SYSTEM,
            )
        )
        result = await action.run(_make_context())

        # Two spawns: audiotee then ffmpeg.
        assert len(seen) == 2
        assert seen[0][0] == "/fake/audiotee"
        assert seen[1][0] == "ffmpeg"

        # ffmpeg has to be told the audiotee output format up front (f32le/48k/mono).
        ff_argv = seen[1]
        assert "f32le" in ff_argv
        assert "48000" in ff_argv
        assert "1" in ff_argv  # mono

        async for _ in result["audio"]:
            pass
        await result["audio"].close()


# ---------------------------------------------------------------------------
# Runtime tests — spawn real ffmpeg. Opt-in via SCREEN_CAPTURE_LIVE=1.
# ---------------------------------------------------------------------------


@ffmpeg_required
@live_only
class TestLiveCapture:
    """Actual screen/audio capture. Requires OS permission (macOS Screen Recording,
    Linux Wayland portal, etc.); if the permission dialog is dismissed the streams
    may be empty but no exception is raised."""

    def _display_index(self) -> int:
        """On macOS the 'display' index is really an avfoundation device index,
        which is offset by the number of cameras on the machine. Override via
        SCREEN_CAPTURE_DISPLAY when the default guess is wrong."""
        env = os.environ.get("SCREEN_CAPTURE_DISPLAY")
        if env is not None:
            return int(env)
        return 0

    @pytest.mark.anyio
    async def test_video_capture_produces_chunks(self):
        config = _make_config(
            include_video=True,
            include_audio=False,
            framerate=10,
            display=self._display_index(),
        )
        action = FFmpegScreenCaptureAction(config)
        result = await action.run(_make_context())

        try:
            chunks_seen = 0
            bytes_seen = 0
            start = time.monotonic()
            async for chunk in result["video"]:
                chunks_seen += 1
                bytes_seen += len(chunk)
                if time.monotonic() - start >= 2.0:
                    break
            assert chunks_seen > 0, "expected at least one encoded video chunk"
            assert bytes_seen > 0
        finally:
            await result["video"].close()
            # Give the reader task's finally-block a tick to reap the process.
            await asyncio.sleep(0.3)
            assert subprocess.run(["pgrep", "ffmpeg"], capture_output=True).returncode != 0, (
                "ffmpeg lingered after resource close"
            )

    @pytest.mark.anyio
    @pytest.mark.skipif(
        platform.system() != "Darwin", reason="microphone test is macOS-only for now"
    )
    async def test_microphone_capture_produces_chunks(self):
        config = _make_config(
            include_video=False,
            include_audio=True,
            audio_source=ScreenCaptureAudioSource.MICROPHONE,
        )
        action = FFmpegScreenCaptureAction(config)
        result = await action.run(_make_context())

        try:
            chunks_seen = 0
            start = time.monotonic()
            async for _ in result["audio"]:
                chunks_seen += 1
                if time.monotonic() - start >= 2.0:
                    break
            assert chunks_seen > 0, "expected at least one encoded audio chunk"
        finally:
            await result["audio"].close()
            await asyncio.sleep(0.3)

    @pytest.mark.anyio
    async def test_region_capture_produces_chunks(self):
        # Small region so the crop filter / offset flags actually kick in.
        config = _make_config(
            video_source=ScreenCaptureVideoSource.REGION,
            region=ScreenCaptureRegion(x=0, y=0, width=320, height=240),
            include_video=True,
            include_audio=False,
            framerate=10,
            display=self._display_index(),
        )
        action = FFmpegScreenCaptureAction(config)
        result = await action.run(_make_context())

        try:
            chunks_seen = 0
            bytes_seen = 0
            start = time.monotonic()
            async for chunk in result["video"]:
                chunks_seen += 1
                bytes_seen += len(chunk)
                if time.monotonic() - start >= 2.0:
                    break
            assert chunks_seen > 0, "expected at least one encoded video chunk"
            assert bytes_seen > 0
        finally:
            await result["video"].close()
            await asyncio.sleep(0.3)
            assert subprocess.run(["pgrep", "ffmpeg"], capture_output=True).returncode != 0, (
                "ffmpeg lingered after resource close"
            )
