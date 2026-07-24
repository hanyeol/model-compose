from __future__ import annotations

from typing import Optional, Union, List, Dict, Set, Tuple, Any
from collections.abc import AsyncIterable
from mindor.dsl.schema.component import RtmpPublisherComponentConfig, RtmpPublisherDriver
from mindor.dsl.schema.action import RtmpPublisherActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.streaming.resources import save_stream_to_temporary_file
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.utils.shell import run_command, run_subprocess, kill_process
from mindor.core.logger import logging
from ..base import RtmpPublisherService, register_rtmp_publisher_service
from ..base import ComponentActionContext
from .common import RtmpPublisherAction
import asyncio, os

# Container formats safe to feed through ffmpeg pipe:0. Other formats
# (mp4/mov/mkv/webm/avi/...) or unknown formats are spooled to a temp file
# first so ffmpeg can seek for moov atoms, indexes, etc.
_STREAMABLE_INPUT_FORMATS: Set[str] = {
    "flv", "mpegts", "ts", "mp3", "wav", "flac", "ogg", "opus", "aac",
}

class FFmpegRtmpSessionPublisher:
    """A long-lived ffmpeg process that keeps one RTMP session open.

    Reads a pre-normalized MPEG-TS stream on stdin and re-encodes / muxes
    it to FLV for the RTMP endpoint. Because every video has been transcoded
    into the same codec/profile/resolution/fps/sample-rate before it hits
    this stdin, concatenating video byte streams produces a valid continuous
    MPEG-TS that ffmpeg can consume without PSI or continuity_counter
    complaints.

    The publisher runs `-re` so RTMP output is paced at wall clock speed.
    The persistent process avoids per-video reconnects that YouTube would
    otherwise treat as broadcast interruptions.
    """
    # All videos are transcoded to these targets before being concatenated
    # onto stdin. Fixed parameters mean the resulting MPEG-TS stream keeps
    # a single codec/init across video boundaries, which is what lets simple
    # byte-level concatenation stay valid.
    _DEFAULT_WIDTH: int = 1920
    _DEFAULT_HEIGHT: int = 1080
    _DEFAULT_FPS: int = 30
    _DEFAULT_SAMPLE_RATE: int = 48000
    _DEFAULT_CHANNELS: int = 2

    def __init__(self, id: str, url: str, params: Dict[str, Any]):
        self.id: str = id
        self.url: str = url
        self.params: Dict[str, Any] = params

        self._normalize_spec: Dict[str, int] = self._resolve_normalize_spec(params)
        self._process: Optional[asyncio.subprocess.Process] = None

        # Serialize video publishes — two normalizers writing into the same stdin
        # at once would interleave MPEG-TS packets and corrupt the stream.
        self._publish_lock: asyncio.Lock = asyncio.Lock()
        self._stderr_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Spawn the ffmpeg process and verify it survived startup.

        Raises RuntimeError if ffmpeg exits within the initial grace window
        (typically due to a bad URL, invalid encoding params, or missing
        binary). The caller is responsible for not reusing a failed publisher.
        """
        command = self._build_publish_command()

        logging.info("Starting continuous RTMP publisher for %s", self.url)
        logging.debug("Publish command: %s", " ".join(command))

        self._process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )

        async def _handle_stderr() -> None:
            try:
                while True:
                    line = await self._process.stderr.readline()
                    if not line:
                        return
                    message = line.decode("utf-8", errors="replace").rstrip()
                    if message:
                        logging.info("[rtmp %s] %s", self.url, message)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logging.debug("stderr drain for %s stopped: %s", self.url, e)

        # Drain ffmpeg's stderr continuously in the background — otherwise the
        # OS pipe buffer fills up and ffmpeg blocks on write(2), stalling the
        # entire RTMP session.
        self._stderr_task = asyncio.create_task(_handle_stderr())

        await asyncio.sleep(0.2)
        if self._process.returncode is not None:
            returncode = self._process.returncode
            await self.close()
            raise RuntimeError(
                f"RTMP publisher for {self.url} exited immediately (code {returncode}); "
                f"see log lines tagged [rtmp {self.url}] for details"
            )

    async def publish(
        self,
        video_path: str,
        has_audio: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> None:
        """Normalize a video to standard MPEG-TS and stream its bytes into stdin.

        Every video is transcoded to h264/aac at the target resolution, fps,
        and sample rate before being written. Because all videos share the
        same codec init this way, this process sees them as one continuous
        MPEG-TS — no per-video PSI reset, no continuity_counter jumps.

        Videos are serialized per publisher (via _publish_lock) so their byte
        streams don't interleave on stdin.
        """
        command = self._build_normalize_command(video_path, has_audio)

        async with self._publish_lock:
            logging.info("Publishing video %s to %s", os.path.basename(video_path), self.url)
            logging.debug("Normalize command: %s", " ".join(command))

            normalizer = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            async def _handle_stderr() -> None:
                while True:
                    line = await normalizer.stderr.readline()
                    if not line:
                        return
                    message = line.decode("utf-8", errors="replace").rstrip()
                    if message:
                        logging.info("[normalizer %s] %s", os.path.basename(video_path), message)

            stderr_task = asyncio.create_task(_handle_stderr())

            bytes_written = 0
            try:
                while True:
                    if cancellation_token is not None and cancellation_token.is_cancelled():
                        logging.info("Publish cancelled while streaming %s", video_path)
                        break

                    if not self.is_alive():
                        logging.warning(
                            "RTMP publisher for %s died (exit %s) while publishing %s",
                            self.url, self._process.returncode, video_path,
                        )
                        break

                    chunk = await normalizer.stdout.read(65536)

                    if not chunk:
                        break

                    try:
                        self._process.stdin.write(chunk)
                        await self._process.stdin.drain()
                        bytes_written += len(chunk)
                    except (BrokenPipeError, ConnectionResetError) as e:
                        logging.warning("RTMP publisher for %s disconnected: %s", self.url, e)
                        break
            finally:
                if normalizer.returncode is None:
                    try:
                        normalizer.terminate()
                    except ProcessLookupError:
                        pass
                await normalizer.wait()

                if not stderr_task.done():
                    stderr_task.cancel()
                try:
                    await stderr_task
                except (asyncio.CancelledError, Exception):
                    pass

                if normalizer.returncode not in (0, -15):
                    logging.warning(
                        "Normalizer for %s exited with %d (%d bytes published); see [normalizer %s] log lines",
                        video_path, normalizer.returncode, bytes_written,
                        os.path.basename(video_path),
                    )
                else:
                    logging.info(
                        "Finished publishing %s to %s (%d bytes)", video_path, self.url, bytes_written,
                    )

    async def close(self) -> None:
        if self._process.stdin is not None and not self._process.stdin.is_closing():
            try:
                self._process.stdin.close()
            except Exception:
                pass

        try:
            await asyncio.wait_for(self._process.wait(), timeout=10)
        except asyncio.TimeoutError:
            logging.warning("RTMP publisher %s did not exit within 10s; killing", self.url)
            await kill_process(self._process)

        if self._stderr_task is not None and not self._stderr_task.done():
            self._stderr_task.cancel()
            try:
                await self._stderr_task
            except (asyncio.CancelledError, Exception):
                pass

    def is_alive(self) -> bool:
        return self._process is not None and self._process.returncode is None

    @property
    def exit_code(self) -> Optional[int]:
        return self._process.returncode if self._process is not None else None

    def _resolve_normalize_spec(self, params: Dict[str, Any]) -> Dict[str, int]:
        resolution = params.get("resolution")

        if resolution:
            width, height = map(int, str(resolution).lower().split("x", 1))
        else:
            width  = self._DEFAULT_WIDTH
            height = self._DEFAULT_HEIGHT

        return {
            "width": width,
            "height": height,
            "fps": int(params.get("fps") or self._DEFAULT_FPS),
            "sample_rate": self._DEFAULT_SAMPLE_RATE,
            "channels": self._DEFAULT_CHANNELS,
        }

    def _build_publish_command(self) -> List[str]:
        """Build the persistent ffmpeg command that owns the RTMP session.

        Reads a normalized MPEG-TS stream on stdin (h264/aac from per-video
        normalizers, all with the same codec init), re-encodes into the RTMP
        payload (h264/aac, flv-wrapped), and pushes to the ingest URL.
        `-re` paces the RTMP push at wall-clock speed.
        """
        fps         = self._normalize_spec["fps"]
        sample_rate = self._normalize_spec["sample_rate"]
        channels    = self._normalize_spec["channels"]

        gop = fps * 2  # 2-second GOP — YouTube's recommended max is 4s.

        return [
            "ffmpeg", "-hide_banner",
            "-loglevel", "warning",
            "-thread_queue_size", "1024",
            "-re",
            "-f", "mpegts",
            "-i", "pipe:0",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-tune", "zerolatency",
            "-profile:v", "high",
            "-b:v", self.params.get("video_bitrate") or "4500k",
            "-maxrate", "5000k",
            "-bufsize", "9000k",
            "-g", str(gop),
            "-keyint_min", str(gop),
            "-sc_threshold", "0",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", self.params.get("audio_bitrate") or "160k",
            "-ar", str(sample_rate),
            "-ac", str(channels),
            # AAC's encoder priming leaves a ~40ms gap between the first
            # sample of a new video and the last sample of the previous one.
            # `aresample=async=1` stretches / drops a handful of samples to
            # bridge that gap on the output side so the muxer never sees a
            # backwards DTS. Without this we get "Non-monotonic DTS" and
            # "Queue input is backward in time" warnings for every video
            # boundary even though the resulting stream plays fine.
            "-af", "aresample=async=1",
            "-max_muxing_queue_size", "1024",
            "-f", self.params["format"],
            "-flvflags", "no_duration_filesize",
            self.url,
        ]

    def _build_normalize_command(self, video_path: str, has_audio: bool) -> List[str]:
        """Decode+transcode+mux a video into MPEG-TS on stdout."""
        width       = self._normalize_spec["width"]
        height      = self._normalize_spec["height"]
        fps         = self._normalize_spec["fps"]
        sample_rate = self._normalize_spec["sample_rate"]
        channels    = self._normalize_spec["channels"]

        # `-ar` and `-ac` on the output side already force the target
        # sample rate and channel layout, so we only need aresample here
        # to hand ffmpeg a filter graph that runs the actual conversion.
        af = f"aresample={sample_rate}"
        gop = fps * 2

        # Always emit an audio-bearing MPEG-TS regardless of whether the source
        # video has an audio track. If it does, we normalize it; if it doesn't,
        # we substitute anullsrc (infinite silence) as a second input. Without
        # this, an audio-less video produces MPEG-TS with no audio packets and
        # the publisher's `-re` clock keeps advancing wall time while the
        # audio stream is stuck — YouTube sees a "backward in time" audio
        # lag that never catches up.
        vf = (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,"
            f"setsar=1,fps={fps}"
        )

        if has_audio:
            command = [
                "ffmpeg", "-hide_banner", "-loglevel", "warning",
                "-i", video_path,
                "-vf", vf,
                "-af", af,
                "-map", "0:v",
                "-map", "0:a",
            ]
        else:
            command = [
                "ffmpeg", "-hide_banner", "-loglevel", "warning",
                "-i", video_path,
                "-f", "lavfi",
                "-i", f"anullsrc=channel_layout={self._channel_layout(channels)}:sample_rate={sample_rate}",
                "-vf", vf,
                "-map", "0:v",
                "-map", "1:a",
                "-shortest",
            ]

        command += [
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-profile:v", "high",
            "-pix_fmt", "yuv420p",
            "-g", str(gop),
            "-keyint_min", str(gop),
            "-sc_threshold", "0",
            "-c:a", "aac",
            # Bitrate on the normalizer matters even though the publisher
            # re-encodes: some `-c:a aac` builds default to ~64k when no
            # explicit bitrate is set, and YouTube picks up on the low
            # rate in the intermediate stream and warns about it.
            "-b:a", "160k",
            "-ar", str(sample_rate),
            "-ac", str(channels),
            # -muxdelay/-muxpreload keep the mpegts muxer from waiting on
            # its own buffer before emitting, so the publisher starts
            # receiving bytes as soon as encoding starts.
            "-muxdelay", "0",
            "-muxpreload", "0",
            "-f", "mpegts",
            "pipe:1",
        ]

        return command

    @staticmethod
    def _channel_layout(channels: int) -> str:
        return { 1: "mono", 2: "stereo" }.get(channels, "stereo")

class FFmpegRtmpSimplePublisher:
    """A simple RTMP publish: spawn ffmpeg, publish once, exit.

    Unlike the session publisher there is no persistent ffmpeg process —
    each `publish()` call spawns a fresh ffmpeg that reads its input(s),
    pushes to RTMP, and terminates. Suitable when the caller has a single
    finite video/audio to broadcast.
    """
    def __init__(self, url: str, params: Dict[str, Any]):
        self.url: str = url
        self.params: Dict[str, Any] = params

    async def publish(
        self,
        video: Optional[Union[MediaSource, str]],
        video_attrs: Optional[Dict[str, Any]],
        audio: Optional[Union[MediaSource, str]],
        audio_attrs: Optional[Dict[str, Any]],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> None:
        has_video = video is not None
        has_audio = audio is not None

        command = [ "ffmpeg", "-hide_banner", "-y" ]

        if has_video:
            if video_attrs and video_attrs.get("resolution"):
                command.extend([ "-s", str(video_attrs["resolution"]) ])
            if video_attrs and video_attrs.get("fps"):
                command.extend([ "-r", str(video_attrs["fps"]) ])
            command.extend([ "-i", video if isinstance(video, str) else "pipe:0" ])

        if has_audio:
            command.extend([ "-i", audio if isinstance(audio, str) else "pipe:0" ])
            if has_video:
                command.extend([ "-map", "0:v", "-map", "1:a", "-shortest" ])

        for option, value in self._resolve_encoding_options(has_video=has_video, has_audio=has_audio).items():
            command.extend([ option, value ])

        command.extend([ "-f", self.params["format"], self.url ])

        source = self._resolve_source(video, audio)

        logging.debug(f"Publishing to RTMP: {self.url}")

        await self._run_process(command, source, cancellation_token)

    def _resolve_source(
        self,
        video: Optional[Union[MediaSource, str]],
        audio: Optional[Union[MediaSource, str]],
    ) -> Optional[AsyncIterable[bytes]]:
        """Return the byte stream to feed on stdin when the input isn't a file path.

        ffmpeg only accepts one `pipe:0` input, so we pick video's stream when
        both are present, and fall back to audio's stream only when there is
        no video at all.
        """
        if isinstance(video, MediaSource):
            return video.stream

        if video is None and isinstance(audio, MediaSource):
            return audio.stream

        return None

    def _resolve_encoding_options(self, has_video: bool, has_audio: bool) -> Dict[str, str]:
        options: Dict[str, str] = {}

        if has_video:
            if self.params["video_codec"]:
                options["-c:v"] = self.params["video_codec"]

            if self.params["video_bitrate"]:
                options["-b:v"] = self.params["video_bitrate"]

            if self.params["resolution"]:
                options["-s"] = self.params["resolution"]

            if self.params["fps"]:
                options["-r"] = str(self.params["fps"])

            if self.params["video_codec"] in ("libx264", "libx265"):
                options["-pix_fmt"] = "yuv420p"

        if has_audio:
            if self.params["audio_codec"]:
                options["-c:a"] = self.params["audio_codec"]

            if self.params["audio_bitrate"]:
                options["-b:a"] = self.params["audio_bitrate"]

        return options

    async def _run_process(
        self,
        command: List[str],
        source: Optional[AsyncIterable[bytes]],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> None:
        # run_subprocess only reacts to asyncio cancellation, but our
        # CancellationToken is a threading.Event that has to be polled.
        # Wrap the ffmpeg run in a task and cancel it when the token fires;
        # run_subprocess then kills the process on its way out.
        process_task = asyncio.create_task(run_subprocess(
            command,
            source,
            stderr_handler=lambda r: r.read(),
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
                raise RuntimeError(f"ffmpeg RTMP publish failed (exit code {process.returncode}): {error_message}")

            logging.debug(f"RTMP publish completed: {self.url}")
        except asyncio.CancelledError:
            logging.info("RTMP publish cancelled for %s", self.url)
            raise
        finally:
            if watcher_task is not None and not watcher_task.done():
                watcher_task.cancel()
                try:
                    await watcher_task
                except (asyncio.CancelledError, Exception):
                    pass

class FFmpegRtmpSessionManager:
    """Owns persistent RTMP session publishers keyed by session id.

    Held by the Service and shared across every Action so that repeated
    invocations for the same session reuse the same ffmpeg process rather
    than reconnecting to RTMP per video.
    """
    def __init__(self):
        self._publishers: Dict[str, FFmpegRtmpSessionPublisher] = {}
        self._lock: asyncio.Lock = asyncio.Lock()

    async def get_or_create(self, session_id: str, url: str, params: Dict[str, Any]) -> FFmpegRtmpSessionPublisher:
        async with self._lock:
            publisher = self._publishers.get(session_id)

            if publisher is not None:
                if publisher.is_alive():
                    return publisher

                logging.warning(
                    "RTMP publisher for %s exited (code %s); restarting",
                    publisher.url, publisher.exit_code,
                )
                del self._publishers[session_id]
                try:
                    await publisher.close()
                except Exception:
                    pass

            publisher = FFmpegRtmpSessionPublisher(session_id, url, params)
            await publisher.start()
            self._publishers[session_id] = publisher

            return publisher

    async def close(self, session_id: str) -> None:
        """Tear down a single session publisher and drop it from the map."""
        async with self._lock:
            publisher = self._publishers.pop(session_id, None)

        if publisher is not None:
            try:
                await publisher.close()
            except Exception as e:
                logging.warning("Error closing RTMP publisher %s: %s", publisher.url, e)

    async def teardown(self) -> None:
        async with self._lock:
            publishers = list(self._publishers.values())
            self._publishers.clear()

        for publisher in publishers:
            try:
                await publisher.close()
            except Exception as e:
                logging.warning("Error closing RTMP publisher %s: %s", publisher.url, e)

class FFmpegRtmpPublisherAction(RtmpPublisherAction):
    def __init__(self, config: RtmpPublisherActionConfig, session_manager: FFmpegRtmpSessionManager):
        super().__init__(config)

        self.session_manager: FFmpegRtmpSessionManager = session_manager

    async def _publish(
        self,
        video: Optional[MediaSource],
        audio: Optional[MediaSource],
        url: str,
        session: Optional[str],
        params: Dict[str, Any],
        loop: asyncio.AbstractEventLoop,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> None:
        if session is not None:
            await self._publish_continuous(video, audio, url, session, params, loop, cancellation_token)
            return

        await self._publish_one_shot(video, audio, url, params, loop, cancellation_token)

    async def _cleanup(self, session: str) -> None:
        await self.session_manager.close(session)

    async def _publish_continuous(
        self,
        video: Optional[MediaSource],
        audio: Optional[MediaSource],
        url: str,
        session: str,
        params: Dict[str, Any],
        loop: asyncio.AbstractEventLoop,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> None:
        """Publish one video into the persistent session publisher.

        The caller (`run`) drives the batch loop and passes videos one at a
        time. Session teardown is orchestrated by `_cleanup`, invoked from
        `run` once the batch loop finishes.
        """
        if video is None:
            return

        publisher = await self.session_manager.get_or_create(session, url, params)
        video_path, spooled = await self._resolve_input_path(video)

        try:
            has_audio_track = await self._probe_has_audio(video_path)
            await publisher.publish(video_path, has_audio_track, cancellation_token)
        finally:
            if spooled and video_path is not None:
                try:
                    os.remove(video_path)
                except FileNotFoundError:
                    pass

    async def _publish_one_shot(
        self,
        video: Optional[MediaSource],
        audio: Optional[MediaSource],
        url: str,
        params: Dict[str, Any],
        loop: asyncio.AbstractEventLoop,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> None:
        video_path, video_spooled = (None, False)
        audio_path, audio_spooled = (None, False)

        if video is not None:
            video_path, video_spooled = await self._resolve_input_path(video)

        if audio is not None:
            audio_path, audio_spooled = await self._resolve_input_path(audio)

        try:
            publisher = FFmpegRtmpSimplePublisher(url, params)
            await publisher.publish(
                video_path if video_path is not None else video,
                video.attrs if video is not None else None,
                audio_path if audio_path is not None else audio,
                audio.attrs if audio is not None else None,
                cancellation_token,
            )
        finally:
            if video_spooled and video_path is not None:
                try:
                    os.remove(video_path)
                except FileNotFoundError:
                    pass
            if audio_spooled and audio_path is not None:
                try:
                    os.remove(audio_path)
                except FileNotFoundError:
                    pass

    async def _resolve_input_path(self, source: MediaSource) -> Tuple[Optional[str], bool]:
        """
        Decide how ffmpeg should read the input.

        - FileStreamResource: use its path directly (no spooling).
        - Streamable format (flv, mpegts, mp3, wav, ...): feed via pipe:0 (returns None path).
        - Otherwise (mp4/mov/unknown/...): spool to a temp file so ffmpeg can seek.

        Returns (input_path, spooled) — spooled=True means the caller owns the temp file cleanup.
        """
        if isinstance(source.stream, FileStreamResource):
            return source.stream.path, False

        if source.format and source.format.lower() in _STREAMABLE_INPUT_FORMATS:
            return None, False

        logging.debug("ffmpeg input is not streamable; spooling to a temp file before publishing")

        spooled_path = await save_stream_to_temporary_file(source.stream, source.format)

        return spooled_path, True

    async def _probe_has_audio(self, path: str) -> bool:
        """Return True when the video carries at least one audio stream."""
        stdout, _, returncode = await run_command([
            "ffprobe", "-v", "error",
            "-select_streams", "a",
            "-show_entries", "stream=codec_type",
            "-of", "csv=p=0",
            path,
        ])
        return returncode == 0 and stdout.strip() != b""

@register_rtmp_publisher_service(RtmpPublisherDriver.FFMPEG)
class FFmpegRtmpPublisherService(RtmpPublisherService):
    def __init__(self, id: str, config: RtmpPublisherComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.session_manager: FFmpegRtmpSessionManager = FFmpegRtmpSessionManager()

    async def _stop(self) -> None:
        await self.session_manager.teardown()

        await super()._stop()

    async def _run(self, action: RtmpPublisherActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        return await FFmpegRtmpPublisherAction(action, self.session_manager).run(context, loop)
