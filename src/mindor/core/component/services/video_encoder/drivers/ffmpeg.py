from __future__ import annotations

from typing import Optional, Tuple, List, Dict, Callable, Any
from collections.abc import AsyncIterator, AsyncIterable
from mindor.dsl.schema.component import VideoEncoderComponentConfig, VideoEncoderDriverType
from mindor.dsl.schema.action import VideoEncoderActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.media.encoding import VideoAudioEncodingParams
from mindor.core.foundation.streaming.video import VideoStreamResource
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.streaming.image import ImageStreamResource
from mindor.core.foundation.streaming.resources import AsyncIterableStreamResource, save_stream_to_temporary_file
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.foundation.variable.array import ArrayValue
from mindor.core.utils.channels.subprocess_stream import SubprocessStreamChannel
from mindor.core.utils.iterators import async_zip
from mindor.core.utils.ffmpeg.executable import resolve_ffmpeg_executable
from mindor.core.utils.ffmpeg.probe import probe_video
from mindor.core.utils.ffmpeg.codecs import (
    get_alpha_containers_for_codec,
    get_alpha_input_decoder,
    get_supported_pixel_formats,
    get_video_codecs_for_format,
    has_alpha_channel,
    encoder_supports_yuv_pixel_format,
    is_yuv_pixel_format,
)
from mindor.core.utils.video import is_streamable_video_format
from mindor.core.utils.files import get_temporary_path
from mindor.core.utils.shell import run_subprocess, stream_subprocess
from mindor.core.utils.time import parse_timecode
from mindor.core.logger import logging
from ....action.media import MediaInputPathResolver
from ..base import VideoEncoderDriver, register_video_encoder_driver
from ..base import ComponentActionContext
from .common import VideoEncoderAction
import asyncio, os

_DEFAULT_FORMAT = "mp4"

# `pass_fds` and inherited pipe descriptors are POSIX-only; Windows can't
# hand a `pipe:<fd>` beyond stdin to a child. When False, callers must spool
# the second live stream to a temp file so ffmpeg reads it as a file input.
_SUPPORTS_FD_INPUT: bool = os.name == "posix"

class FFmpegVideoEncoderAction(VideoEncoderAction):
    async def _encode_from_video(
        self,
        video: MediaSource,
        audio: Optional[MediaSource],
        encoding: VideoAudioEncodingParams,
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> VideoStreamResource:
        format = self._resolve_container_format(encoding)

        if streaming and not is_streamable_video_format(format):
            logging.warning("Format '%s' is not streamable; falling back to file output.", format)
            streaming = False

        video_path, video_spooled = await MediaInputPathResolver().resolve(video, streamable_media=[ "video" ])
        audio_path, audio_spooled = (await MediaInputPathResolver().resolve(audio, streamable_media=[ "audio", "video" ])) if audio is not None else (None, False)

        # webm/mkv can carry VP8/VP9 side-data alpha; the ffprobe check + the
        # `-c:v libvpx*` decoder override both require a file path. Force-spool
        # so alpha isn't lost when the source arrives as a pipe.
        if video_path is None and video.format and video.format.lower() in ("webm", "mkv"):
            video_path = await save_stream_to_temporary_file(video.stream, video.format)
            video_spooled = True

        # On Windows only `pipe:0` is available. If both sides would end up as
        # live streams, force-spool the audio side so the video keeps its pipe path.
        if not _SUPPORTS_FD_INPUT and audio is not None:
            if video_path is None and audio_path is None:
                audio_path = await save_stream_to_temporary_file(audio.stream, audio.format)
                audio_spooled = True

        # The first live stream takes stdin (`pipe:0`); any further one rides an
        # inherited descriptor (POSIX-only). File paths are resolved to themselves.
        stdin_owner: Optional[MediaSource] = None
        fd_channels: List[SubprocessStreamChannel] = []

        video_input, stdin_owner = self._resolve_input_source(video, video_path, stdin_owner, fd_channels)
        audio_input, stdin_owner = self._resolve_input_source(audio, audio_path, stdin_owner, fd_channels) if audio is not None else (None, stdin_owner)

        command = [ resolve_ffmpeg_executable(), "-hide_banner", "-y" ]

        if video.attrs.get("resolution"):
            command.extend([ "-s", str(video.attrs["resolution"]) ])

        if video.attrs.get("frame_rate"):
            command.extend([ "-r", str(video.attrs["frame_rate"]) ])

        # VP8/VP9 side-data alpha is silently dropped by the native decoder;
        # force libvpx*/libvpx-vp9 when the source carries it so the alpha
        # channel actually reaches the encoder. Only viable with a file input
        # (probing needs a path).
        if video_path is not None:
            codec, alpha_mode = await probe_video(video_path, ("codec", "alpha_mode"))
            alpha_decoder = get_alpha_input_decoder(codec, alpha_mode)

            if alpha_decoder is not None:
                command.extend([ "-c:v", alpha_decoder ])

        command.extend([ "-i", video_input ])

        if audio_input is not None:
            command.extend([ "-i", audio_input ])
            # `?` makes the audio map optional so an audio input without an
            # audio stream (video-only file passed as `audio`) doesn't crash;
            # the encoder still runs and just produces a video-only output.
            command.extend([ "-map", "0:v", "-map", "1:a?" ])

        for option, value in self._resolve_encoding_options(encoding, has_audio=audio_input is not None).items():
            command.extend([ option, value ])

        if audio_input is not None:
            command.append("-shortest")

        def _cleanup() -> None:
            if video_spooled:
                try:
                    os.remove(video_path)
                except FileNotFoundError:
                    pass

            if audio_spooled:
                try:
                    os.remove(audio_path)
                except FileNotFoundError:
                    pass

        source = stdin_owner.stream if stdin_owner is not None else None

        logging.debug("Encoding video to '%s'", format)

        if streaming:
            return await self._encode_to_stream(command, source, fd_channels, format, _cleanup, cancellation_token)

        return await self._encode_to_file(command, source, fd_channels, format, _cleanup, cancellation_token)

    async def _encode_from_frames(
        self,
        frames: AsyncIterable[ImageStreamResource],
        audio: Optional[MediaSource],
        encoding: VideoAudioEncodingParams,
        frame_rate: Optional[float],
        timestamps: Optional[ArrayValue],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> VideoStreamResource:
        format = encoding.format or _DEFAULT_FORMAT
        frame_rate = frame_rate or 30

        if streaming and not is_streamable_video_format(format.lower()):
            logging.warning("Format '%s' is not streamable; falling back to file output.", format)
            streaming = False

        audio_path, audio_spooled = (await MediaInputPathResolver().resolve(audio, streamable_media=[ "audio", "video" ])) if audio is not None else (None, False)

        # `image2pipe` already claims stdin. If audio remains a live stream, it
        # needs an inherited descriptor — POSIX-only. Force-spool on Windows.
        if not _SUPPORTS_FD_INPUT and audio is not None and audio_path is None:
            audio_path = await save_stream_to_temporary_file(audio.stream, audio.format)
            audio_spooled = True

        fd_channels: List[SubprocessStreamChannel] = []
        audio_input: Optional[str] = None

        if audio is not None:
            if audio_path is not None:
                audio_input = audio_path
            else:
                channel = SubprocessStreamChannel(audio.stream)
                fd_channels.append(channel)
                audio_input = f"pipe:{channel.read_fd}"

        # Peek the first frame for the source height — needed to pick the BT.709/601 matrix
        # before the ffmpeg process starts. `encoding.resolution` wins when set.
        frames_iterator = frames.__aiter__()
        first_frame = await self._peek_next_frame(frames_iterator)
        source_height = await self._resolve_source_height(encoding, first_frame)

        command = [ resolve_ffmpeg_executable(), "-hide_banner", "-y" ]
        command.extend([ "-f", "image2pipe", "-framerate", str(frame_rate), "-i", "pipe:0" ])

        if audio_input is not None:
            command.extend([ "-i", audio_input ])
            # `?` makes the audio map optional so an audio input without an
            # audio stream (video-only file passed as `audio`) doesn't crash;
            # the encoder still runs and just produces a video-only output.
            command.extend([ "-map", "0:v", "-map", "1:a?" ])

        for option, value in self._resolve_encoding_options(encoding, has_audio=audio_input is not None, source_height=source_height).items():
            command.extend([ option, value ])

        if audio_input is not None:
            command.append("-shortest")

        def _cleanup() -> None:
            if audio_spooled:
                try:
                    os.remove(audio_path)
                except FileNotFoundError:
                    pass

        async def _stream_frames() -> AsyncIterator[ImageStreamResource]:
            # Rejoin the peeked first frame with the rest of the iterator so
            # downstream consumers see one unbroken frame stream.
            if first_frame is not None:
                yield first_frame

            async for frame in frames_iterator:
                yield frame

        async def _source_iterator() -> AsyncIterator[bytes]:
            if timestamps is not None:
                # VFR → CFR pacing: emit each frame `round(t[i+1]*fps) - round(t[i]*fps)` times.
                # The first timestamp is normalized to 0, so audio muxed separately may need its own offset.
                # The final frame has no successor to size against; repeat it by the prior interval so
                # a run of N evenly-spaced timestamps covers N full slots instead of N-1 + 1.
                first_timestamp: Optional[float] = None
                previous_frame_bytes: Optional[bytes] = None
                previous_frame_index = 0
                previous_timestamp = 0.0
                last_interval = 0

                async for frame, timestamp in async_zip(_stream_frames(), timestamps):
                    timestamp = parse_timecode(timestamp) if isinstance(timestamp, str) else float(timestamp)

                    if first_timestamp is None:
                        first_timestamp = timestamp

                    timestamp -= first_timestamp

                    if timestamp < previous_timestamp:
                        raise ValueError(
                            f"timestamps must be non-decreasing; got {timestamp + first_timestamp} "
                            f"after {previous_timestamp + first_timestamp}"
                        )

                    current_frame_index = round(timestamp * float(frame_rate))

                    if previous_frame_bytes is not None:
                        interval = current_frame_index - previous_frame_index

                        for _ in range(interval):
                            yield previous_frame_bytes

                        if interval > 0:
                            last_interval = interval

                    frame_bytes = bytearray()

                    async with frame:
                        async for chunk in frame:
                            frame_bytes.extend(chunk)

                    previous_frame_bytes = bytes(frame_bytes)
                    previous_frame_index = current_frame_index
                    previous_timestamp = timestamp

                if previous_frame_bytes is not None:
                    tail = last_interval if last_interval > 0 else 1

                    for _ in range(tail):
                        yield previous_frame_bytes
            else:
                # No timestamps: CFR path — pipe raw frame bytes through at `frame_rate`.
                async for frame in _stream_frames():
                    async with frame:
                        async for chunk in frame:
                            yield chunk

        source = _source_iterator()

        logging.debug("Encoding frames to '%s'", format)

        if streaming:
            return await self._encode_to_stream(command, source, fd_channels, format, _cleanup, cancellation_token)

        return await self._encode_to_file(command, source, fd_channels, format, _cleanup, cancellation_token)

    async def _encode_to_file(
        self,
        command: List[str],
        source: Optional[AsyncIterable[bytes]],
        fd_channels: List[SubprocessStreamChannel],
        format: str,
        cleanup: Callable[[], None],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> VideoStreamResource:
        """Run ffmpeg to a temporary file, then return a VideoStreamResource over that file."""
        output_path = get_temporary_path(format)

        # `+faststart` moves the moov atom to the front so mp4/mov files start
        # playing before the whole file is downloaded. It's an ISO-BMFF-only
        # feature — webm/mkv/etc. ignore or reject it, so gate on container.
        if format in ("mp4", "mov", "m4v"):
            command = command + [ "-movflags", "+faststart" ]

        command = command + [ output_path ]

        async def _on_started() -> None:
            # ffmpeg owns the read ends now; each start() drops the parent's
            # copy so ffmpeg can see EOF, then begins pumping the source.
            for channel in fd_channels:
                await channel.start()

        # run_subprocess only reacts to asyncio cancellation, but our
        # CancellationToken is a threading.Event that has to be polled.
        # Wrap the ffmpeg run in a task and cancel it when the token fires;
        # run_subprocess then kills the process on its way out.
        process_task = asyncio.create_task(run_subprocess(
            command,
            source,
            stderr_handler=lambda r: r.read(),
            pass_fds=tuple(channel.read_fd for channel in fd_channels),
            on_started=_on_started,
        ))

        watcher_task: Optional[asyncio.Task] = None

        if cancellation_token is not None:
            async def _watch_cancellation() -> None:
                while not cancellation_token.is_cancelled():
                    if process_task.done():
                        return
                    await asyncio.sleep(0.2)
                process_task.cancel()

            watcher_task = asyncio.create_task(_watch_cancellation())

        try:
            process, _, error = await process_task

            if process.returncode != 0:
                error_message = error.decode("utf-8", errors="replace") if error else ""
                raise RuntimeError(f"ffmpeg video encoding failed (exit code {process.returncode}): {error_message}")
        except asyncio.CancelledError:
            logging.info("Video encoding cancelled")
            raise
        finally:
            if watcher_task is not None and not watcher_task.done():
                watcher_task.cancel()
                try:
                    await watcher_task
                except (asyncio.CancelledError, Exception):
                    pass

            for channel in fd_channels:
                await channel.close()

            cleanup()

        logging.debug("Video encoding completed: '%s'", output_path)

        return VideoStreamResource(FileStreamResource(output_path, auto_delete=True), format=format)

    async def _encode_to_stream(
        self,
        command: List[str],
        source: Optional[AsyncIterable[bytes]],
        fd_channels: List[SubprocessStreamChannel],
        format: str,
        cleanup: Callable[[], None],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> VideoStreamResource:
        """Run ffmpeg writing to stdout and wrap the byte stream as a VideoStreamResource."""
        command = command + [ "-f", format, "pipe:1" ]
        error: list = []

        async def _handle_stdout(reader: asyncio.StreamReader) -> AsyncIterator[bytes]:
            while True:
                chunk = await reader.read(65536)

                if not chunk:
                    break

                yield chunk

        async def _handle_stderr(reader: asyncio.StreamReader) -> None:
            while True:
                line = await reader.readline()

                if not line:
                    break

                error.append(line)

        async def _on_started() -> None:
            # ffmpeg owns the read ends now; each start() drops the parent's
            # copy so ffmpeg can see EOF, then begins pumping the source.
            for channel in fd_channels:
                await channel.start()

        async def _stream() -> AsyncIterator[bytes]:
            watcher_task: Optional[asyncio.Task] = None
            try:
                async with stream_subprocess(
                    command,
                    stdin=source,
                    stdout_handler=_handle_stdout,
                    stderr_handler=_handle_stderr,
                    pass_fds=tuple(channel.read_fd for channel in fd_channels),
                    on_started=_on_started,
                ) as (process, chunks, _):
                    if cancellation_token is not None:
                        async def _watch_cancellation() -> None:
                            while not cancellation_token.is_cancelled():
                                if process.returncode is not None:
                                    return
                                await asyncio.sleep(0.2)
                            process.kill()

                        watcher_task = asyncio.create_task(_watch_cancellation())

                    async for chunk in chunks:
                        yield chunk

                if process.returncode is not None and process.returncode != 0:
                    error_message = b"".join(error).decode("utf-8", errors="replace")
                    raise RuntimeError(f"ffmpeg video encoding failed (exit code {process.returncode}): {error_message}")
            finally:
                if watcher_task is not None and not watcher_task.done():
                    watcher_task.cancel()
                    try:
                        await watcher_task
                    except (asyncio.CancelledError, Exception):
                        pass

                for channel in fd_channels:
                    await channel.close()

                cleanup()

        return VideoStreamResource(AsyncIterableStreamResource(_stream()), format=format)

    @staticmethod
    async def _peek_next_frame(iterator: AsyncIterator[ImageStreamResource]) -> Optional[ImageStreamResource]:
        """Pull one frame from an async iterator or return None if it's exhausted."""
        try:
            return await iterator.__anext__()
        except StopAsyncIteration:
            return None

    @staticmethod
    async def _resolve_source_height(
        encoding: VideoAudioEncodingParams,
        first_frame: Optional[ImageStreamResource],
    ) -> Optional[int]:
        """Pick the height that drives BT.709/601 selection.

        `encoding.video.resolution` wins when set — a 640×360 source encoded to
        1280×720 outputs HD and needs 709 tagging even though the first frame
        is SD. Falls back to the first frame's pixel height when resolution is
        left unspecified.
        """
        if encoding.video and encoding.video.resolution:
            _, _, height = encoding.video.resolution.partition("x")
            if height.isdigit():
                return int(height)

        if first_frame is not None:
            return (await first_frame.as_image()).size[1]

        return None

    @staticmethod
    def _resolve_input_source(
        media: MediaSource,
        media_path: Optional[str],
        stdin_owner: Optional[MediaSource],
        fd_channels: List[SubprocessStreamChannel],
    ) -> Tuple[str, Optional[MediaSource]]:
        """Assign one input to a file path, `pipe:0`, or an inherited descriptor.

        `media_path` is the result of `_resolve_input_path` — a real path if the
        source was spooled or already on disk, or None if it should be fed as a
        live stream. Live streams take stdin (`pipe:0`) first; any further one
        rides an inherited fd, which is POSIX-only.
        """
        if media_path is not None:
            return media_path, stdin_owner

        if stdin_owner is None:
            return "pipe:0", media

        if not _SUPPORTS_FD_INPUT:
            raise RuntimeError(
                "Multiple live streams are not supported on this platform; "
                "spool one input to a file before encoding."
            )

        channel = SubprocessStreamChannel(media.stream)
        fd_channels.append(channel)

        return f"pipe:{channel.read_fd}", stdin_owner

    def _resolve_encoding_options(
        self,
        encoding: VideoAudioEncodingParams,
        has_audio: bool,
        source_height: Optional[int] = None,
    ) -> Dict[str, str]:
        """Build the ffmpeg option dict for one encode.

        `source_height` is the input height in pixels when it's known ahead of
        time (frames path — first-frame lookahead). It's used to (a) pick the
        color matrix for RGB→YUV conversion and (b) tag the stream to match.
        Video-input path passes None, since ffmpeg preserves the source's own
        color tags and forcing 709 on an SD (601) source would be wrong.
        """
        options: Dict[str, str] = {}

        video = encoding.video
        audio = encoding.audio

        video_codec = self._resolve_video_codec(encoding)

        if video_codec:
            options["-c:v"] = video_codec

        if video and video.quality is not None:
            options["-crf"] = str(video.quality)
        elif video and video.bitrate:
            options["-b:v"] = str(video.bitrate)

        if video and video.resolution:
            options["-s"] = video.resolution

        if video and video.frame_rate is not None:
            options["-r"] = str(video.frame_rate)

        pixel_format = self._resolve_pixel_format(encoding, video_codec, force_yuv=source_height is not None)
        filters: List[str] = []

        if pixel_format is not None:
            options["-pix_fmt"] = pixel_format

            # yuv420p (4:2:0 subsampling) requires even dimensions; ffmpeg
            # errors on odd width/height. Pad up to the next even pixel with
            # black — a no-op on already-even sources — so callers don't have
            # to worry about source dimensions.
            if pixel_format == "yuv420p":
                filters.append("pad=ceil(iw/2)*2:ceil(ih/2)*2:color=black")

            # libvpx (VP8) refuses to encode alpha unless auto_alt_ref is
            # disabled — otherwise it aborts with "Transparency encoding with
            # auto_alt_ref does not work". Set the flag transparently so alpha
            # pipelines "just work".
            if video_codec == "libvpx" and has_alpha_channel(pixel_format):
                options["-auto-alt-ref"] = "0"

        # Color-matrix conversion + tagging (frames path only). ffmpeg's
        # default swscale converts RGB → YUV with a BT.601 matrix regardless
        # of resolution, so HD frames come out wrong on players that assume
        # 709 for HD. Force the matrix explicitly and tag the stream to match.
        color_matrix = self._resolve_color_matrix(video_codec, pixel_format, source_height)

        if color_matrix is not None:
            filters.append(f"scale=out_color_matrix={color_matrix}:out_range=tv")

            # Pin the pixel-format conversion to this filter graph so ffmpeg's
            # negotiator can't insert its own (default-601) scale after us.
            if pixel_format is not None:
                filters.append(f"format={pixel_format}")

            # `setparams` writes the color metadata onto every frame — encoders
            # then propagate it into the bitstream's VUI. Works across codecs
            # (x264/x265/vpx) and ffmpeg versions without per-encoder params.
            # The output flags below are belt-and-suspenders for muxer metadata.
            filters.append(f"setparams=color_primaries={color_matrix}:color_trc={color_matrix}:colorspace={color_matrix}:range=tv")

            options["-color_primaries"] = color_matrix
            options["-color_trc"]       = color_matrix
            options["-colorspace"]      = color_matrix
            options["-color_range"]     = "tv"

        if filters:
            options["-vf"] = ",".join(filters)

        if has_audio:
            audio_codec = self._resolve_audio_codec(encoding)

            if audio_codec:
                options["-c:a"] = audio_codec

            if audio and audio.bitrate:
                options["-b:a"] = str(audio.bitrate)

        return options

    @staticmethod
    def _resolve_color_matrix(
        video_codec: Optional[str],
        pixel_format: Optional[str],
        source_height: Optional[int],
    ) -> Optional[str]:
        """Pick the color matrix for RGB→YUV conversion, or None to skip.

        Only applies when the caller supplied a source height (frames path)
        and the output is definitely YUV. When `pixel_format` isn't known,
        fall back to the encoder's supported list — encoders with no YUV
        formats (gif, png) never get tagged.
        """
        if source_height is None:
            return None

        if pixel_format is not None:
            if not is_yuv_pixel_format(pixel_format):
                return None
        else:
            if video_codec is None or not encoder_supports_yuv_pixel_format(video_codec):
                return None

        # BT.709 is the HDTV standard (≥720p); SD stays on BT.601 so players
        # that ignore stream tags and assume 601-for-SD still render correctly.
        return "bt709" if source_height >= 720 else "smpte170m"

    def _resolve_pixel_format(
        self,
        encoding: VideoAudioEncodingParams,
        video_codec: Optional[str],
        force_yuv: bool = False,
    ) -> Optional[str]:
        """Pick and validate the output pixel format.

        User-supplied `pixel_format` is checked against the encoder's known
        supported list (per `codecs.py`) and against known silent-drop
        codec/container pairings (VP9-alpha only works in webm/mkv; mp4
        would silently drop alpha).

        When `pixel_format` is unset:
        - `force_yuv=True` (frames path): pin any YUV-capable encoder to yuv420p
          so libx265/libvpx-vp9 don't silently pick gbrp for RGB input.
        - `force_yuv=False` (video path): keep the old x264/x265 → yuv420p
          default; other encoders inherit ffmpeg's negotiation from the source.
        """
        pixel_format = encoding.video.pixel_format if encoding.video else None

        if pixel_format is None:
            if force_yuv and video_codec and encoder_supports_yuv_pixel_format(video_codec):
                return "yuv420p"

            # Backwards-compatible default: yuv420p for x264/x265 image-derived streams.
            return "yuv420p" if video_codec in ("libx264", "libx265") else None

        if video_codec:
            supported = get_supported_pixel_formats(video_codec)

            if supported is not None and pixel_format not in supported:
                raise ValueError(
                    f"Encoder '{video_codec}' does not support pixel_format '{pixel_format}'; "
                    f"supported formats: {', '.join(sorted(supported))}"
                )

        if has_alpha_channel(pixel_format):
            container = self._resolve_container_format(encoding)
            allowed_containers = get_alpha_containers_for_codec(video_codec) if video_codec else None

            if allowed_containers is not None and container not in allowed_containers:
                raise ValueError(
                    f"Encoder '{video_codec}' with alpha pixel_format '{pixel_format}' silently drops alpha "
                    f"in container '{container}'; use one of: {', '.join(sorted(allowed_containers))}"
                )

        return pixel_format

    @staticmethod
    def _resolve_container_format(encoding: VideoAudioEncodingParams) -> str:
        if encoding.format:
            return encoding.format.lower()

        return _DEFAULT_FORMAT

    @staticmethod
    def _resolve_video_codec(encoding: VideoAudioEncodingParams) -> Optional[str]:
        if encoding.video and encoding.video.codec:
            return encoding.video.codec

        video_codec, _ = get_video_codecs_for_format(encoding.format or _DEFAULT_FORMAT)

        return video_codec

    @staticmethod
    def _resolve_audio_codec(encoding: VideoAudioEncodingParams) -> Optional[str]:
        if encoding.audio and encoding.audio.codec:
            return encoding.audio.codec

        _, audio_codec = get_video_codecs_for_format(encoding.format or _DEFAULT_FORMAT)

        return audio_codec

@register_video_encoder_driver(VideoEncoderDriverType.FFMPEG)
class FFmpegVideoEncoderService(VideoEncoderDriver):
    def __init__(self, id: str, config: VideoEncoderComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _run(self, action: VideoEncoderActionConfig, context: ComponentActionContext) -> Any:
        return await FFmpegVideoEncoderAction(action).run(context)
