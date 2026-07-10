from typing import Optional, Dict, List, Callable, Awaitable, Any
from collections.abc import AsyncIterator
from abc import ABC, abstractmethod
from ...common import VideoAudioEncodingParams
import asyncio
import ulid

_CONTAINER_MIME_MAP: Dict[str, str] = {
    "webm": "video/webm",
    "mp4":  "video/mp4",
}

# MediaRecorder timeslice (milliseconds): how often ondataavailable fires.
# 1 second is a good trade-off between responsiveness and page-binding overhead.
_DEFAULT_CHUNK_INTERVAL = 1000

# Runs inside the Chromium page. Grabs a MediaStream from the target <video> via
# captureStream(), pipes it into MediaRecorder, and forwards each chunk to the
# Python side over the caller-provided emit binding. Also installs a stop
# function under the caller-provided name so the driver can end the recording.
# Both names are per-capture (ULID-suffixed) to avoid clashing with previous
# captures still registered on the shared page.
_CAPTURE_VIDEO_SCRIPT = """
async ({ selector, include_video_track, include_audio_track, options, chunkInterval, emitBinding, stopBinding }) => {
  const el = selector ? document.querySelector(selector) : document.querySelector('video');
  if (!el) {
    throw new Error(selector ? `No element matches selector: ${selector}` : 'No <video> element found on the page');
  }
  if (typeof el.captureStream !== 'function') {
    throw new Error('The selected element does not support captureStream()');
  }
  if (el.readyState < 2) {
    await new Promise((resolve, reject) => {
      const onReady = () => { cleanup(); resolve(); };
      const onError = (err) => { cleanup(); reject(err || new Error('Media element failed to load')); };
      const cleanup = () => {
        el.removeEventListener('loadeddata', onReady);
        el.removeEventListener('error', onError);
      };
      el.addEventListener('loadeddata', onReady, { once: true });
      el.addEventListener('error', onError, { once: true });
    });
  }
  if (el.paused) {
    try { await el.play(); } catch (_) { /* autoplay may be blocked; continue if the site handles it */ }
  }
  const sourceStream = el.captureStream();
  const tracks = [];
  if (include_video_track) sourceStream.getVideoTracks().forEach((t) => tracks.push(t));
  if (include_audio_track) sourceStream.getAudioTracks().forEach((t) => tracks.push(t));
  if (tracks.length === 0) {
    throw new Error('No matching tracks on the captured stream (include_video_track/include_audio_track exclude all tracks)');
  }
  const stream = new MediaStream(tracks);
  console.log('[capture-video] tracks =', stream.getTracks().map((t) => t.kind + ':' + (t.label || 'unlabeled')).join(', '));
  const recorder = new MediaRecorder(stream, options);
  recorder.ondataavailable = async (event) => {
    if (event.data && event.data.size > 0) {
      const buffer = await event.data.arrayBuffer();
      const emit = window[emitBinding];
      if (emit) await emit(Array.from(new Uint8Array(buffer)));
    }
  };
  window[stopBinding] = () => new Promise((resolve) => {
    recorder.onstop = () => {
      sourceStream.getTracks().forEach((track) => track.stop());
      resolve();
    };
    recorder.stop();
  });
  // Wait for the first painted frame before starting the recorder so `duration`
  // reflects actual playback time instead of counting from load. Fallback to a
  // short timeout for engines that lack requestVideoFrameCallback.
  if (include_video_track && typeof el.requestVideoFrameCallback === 'function') {
    await new Promise((resolve) => {
      let done = false;
      const settle = () => { if (!done) { done = true; resolve(); } };
      el.requestVideoFrameCallback(settle);
      setTimeout(settle, 2000);
    });
  }
  recorder.start(chunkInterval);
}
"""

# Sentinel placed on VideoRecorder.queue to signal end-of-stream to consumers.
_STREAM_END = object()

class PageAdapter(ABC):
    """Minimal page-driving surface required by VideoRecorder.

    Kept intentionally shaped after Playwright's Page API (goto / expose_binding /
    evaluate) so the Playwright adapter is a no-op wrapper; the CDP adapter
    reproduces the same semantics on top of raw Chrome DevTools Protocol calls.
    """
    @abstractmethod
    async def navigate(self, url: str) -> None:
        pass

    @abstractmethod
    async def expose_binding(
        self,
        name: str,
        callback: Callable[..., Awaitable[None]],
    ) -> None:
        pass

    @abstractmethod
    async def evaluate(self, expression: str, arg: Any = None) -> Any:
        pass

class VideoRecorder:
    """Records video/audio from a <video> element in a Chromium page.

    Uses HTMLMediaElement.captureStream() + MediaRecorder inside the page and
    ferries the encoded chunks back over a page binding. The recorder is
    Chrome/Chromium-specific because it relies on MediaRecorder and page
    bindings; other engines (Firefox/WebKit) need a different implementation.

    The page is accessed through a PageAdapter so this class works both with a
    Playwright Page and a raw CDP client.
    """
    def __init__(self, page: PageAdapter):
        self._page = page

    async def capture(
        self,
        url: Optional[str],
        selector: Optional[str],
        include_video_track: bool,
        include_audio_track: bool,
        encoding: Optional[VideoAudioEncodingParams],
        duration: Optional[float],
    ) -> AsyncIterator[bytes]:
        if url:
            await self._page.navigate(url)

        # Per-capture unique names so multiple captures on the same page don't
        # collide on Playwright's page-binding registration (which has no
        # unregister API and rejects duplicate names).
        capture_id   = ulid.ulid()
        emit_binding = f"__mindorEmitChunk_{capture_id}"
        stop_binding = f"__mindorStopCapture_{capture_id}"

        queue: asyncio.Queue = asyncio.Queue(maxsize=32)
        first_chunk_at: asyncio.Future = asyncio.get_running_loop().create_future()
        stopped = False

        async def _on_video_chunk(_, data: List[int]) -> None:
            if stopped:
                return
            if not first_chunk_at.done():
                first_chunk_at.set_result(None)
            try:
                await queue.put(bytes(data))
            except Exception:
                pass

        await self._page.expose_binding(emit_binding, _on_video_chunk)

        options = self._build_media_recorder_options(include_video_track, include_audio_track, encoding)

        await self._page.evaluate(
            _CAPTURE_VIDEO_SCRIPT,
            {
                "selector": selector,
                "include_video_track": include_video_track,
                "include_audio_track": include_audio_track,
                "options": options,
                "chunkInterval": _DEFAULT_CHUNK_INTERVAL,
                "emitBinding": emit_binding,
                "stopBinding": stop_binding,
            },
        )

        async def _stop() -> None:
            nonlocal stopped
            if stopped:
                return
            stopped = True
            try:
                await self._page.evaluate(
                    f"() => window['{stop_binding}'] && window['{stop_binding}']()"
                )
            except Exception:
                pass
            finally:
                await queue.put(_STREAM_END)

        stop_task: Optional[asyncio.Task] = None
        if duration is not None:
            async def _timed_stop() -> None:
                # Anchor the timer to the first emitted chunk so the requested
                # duration measures actual recorded content, not navigate +
                # encoder-startup latency.
                await first_chunk_at
                await asyncio.sleep(duration)
                await _stop()
            stop_task = asyncio.create_task(_timed_stop())

        try:
            while True:
                item = await queue.get()
                if item is _STREAM_END:
                    break
                yield item
        finally:
            await _stop()
            if stop_task is not None:
                try:
                    await stop_task
                except (asyncio.CancelledError, Exception):
                    pass
            # Neutralize the emit binding so no more CDP round-trips are attempted
            # after we return. Otherwise Playwright may try to invoke the Python
            # handler as the page/context tears down, surfacing as a stray
            # TargetClosedError on the event loop.
            try:
                await self._page.evaluate(
                    f"() => {{ window['{emit_binding}'] = () => {{}}; }}"
                )
            except Exception:
                pass
            # Let any in-flight binding callbacks settle before we hand control
            # back to the caller (who typically closes the page/context next).
            await asyncio.sleep(0)

    @staticmethod
    def _build_media_recorder_options(
        include_video_track: bool,
        include_audio_track: bool,
        encoding: Optional[VideoAudioEncodingParams],
    ) -> Dict[str, Any]:
        """Translate the rendered encoding params into MediaRecorder options."""
        options: Dict[str, Any] = {}

        if encoding is not None:
            container = (encoding.format or "webm").lower()
            base_mime = _CONTAINER_MIME_MAP.get(container, f"video/{container}")

            codecs: List[str] = []
            if include_video_track and encoding.video and encoding.video.codec:
                codecs.append(encoding.video.codec)
            if include_audio_track and encoding.audio and encoding.audio.codec:
                codecs.append(encoding.audio.codec)

            options["mimeType"] = f"{base_mime};codecs={','.join(codecs)}" if codecs else base_mime

            if include_video_track and encoding.video and encoding.video.bitrate is not None:
                options["videoBitsPerSecond"] = encoding.video.bitrate
            if include_audio_track and encoding.audio and encoding.audio.bitrate is not None:
                options["audioBitsPerSecond"] = encoding.audio.bitrate

        return options
