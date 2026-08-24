from __future__ import annotations

from typing import Optional, Union, Tuple, Dict, List, Any
from mindor.dsl.schema.component import MediaDownloaderComponentConfig, MediaDownloaderDriver
from mindor.dsl.schema.action import MediaDownloaderActionConfig
from mindor.core.foundation.streaming.audio import AudioStreamResource
from mindor.core.foundation.streaming.video import VideoStreamResource
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.files import get_temporary_path, get_file_extension
from mindor.core.logger import logging
from ..base import MediaDownloaderService, register_media_downloader_service
from ..base import ComponentActionContext
from .common import MediaDownloaderAction, DownloadResult
import asyncio, os

_FORMAT_PRESETS: Dict[str, Tuple[Dict[str, Any], bool]] = {
    "mp3": ({
        "format": "ba[acodec^=mp3]/ba/b",
        "postprocessors": [{ "key": "FFmpegExtractAudio", "preferredcodec": "mp3" }],
    }, True),

    "aac": ({
        "format": "ba[acodec^=aac]/ba[acodec^=mp4a.40.]/ba/b",
        "postprocessors": [{ "key": "FFmpegExtractAudio", "preferredcodec": "aac" }],
    }, True),

    "m4a": ({
        "format": "ba[ext=m4a]/ba[acodec^=mp4a.40.]/ba/b",
        "postprocessors": [{ "key": "FFmpegExtractAudio", "preferredcodec": "m4a" }],
    }, True),

    "opus": ({
        "format": "ba[acodec=opus]/ba[ext=webm]/ba/b",
        "postprocessors": [{ "key": "FFmpegExtractAudio", "preferredcodec": "opus" }],
    }, True),

    "vorbis": ({
        "format": "ba[acodec=vorbis]/ba/b",
        "postprocessors": [{ "key": "FFmpegExtractAudio", "preferredcodec": "vorbis" }],
    }, True),

    "flac": ({
        "format": "ba/b",
        "postprocessors": [{ "key": "FFmpegExtractAudio", "preferredcodec": "flac" }],
    }, True),

    "alac": ({
        "format": "ba/b",
        "postprocessors": [{ "key": "FFmpegExtractAudio", "preferredcodec": "alac" }],
    }, True),

    "wav": ({
        "format": "ba/b",
        "postprocessors": [{ "key": "FFmpegExtractAudio", "preferredcodec": "wav" }],
    }, True),

    "mp4": ({
        "merge_output_format": "mp4",
        "postprocessors": [{ "key": "FFmpegVideoRemuxer", "preferedformat": "mp4" }],
        "format_sort": [ "vcodec:h264", "lang", "quality", "res", "fps", "hdr:12", "acodec:aac" ],
    }, False),

    "mkv": ({
        "merge_output_format": "mkv",
        "postprocessors": [{ "key": "FFmpegVideoRemuxer", "preferedformat": "mkv" }],
    }, False),

    "webm": ({
        "merge_output_format": "webm",
        "postprocessors": [{ "key": "FFmpegVideoRemuxer", "preferedformat": "webm" }],
        "format_sort": [ "vcodec:vp9", "lang", "quality", "res", "fps", "acodec:opus" ],
    }, False),
}

class YtdlpMediaDownloaderAction(MediaDownloaderAction):
    async def _resolve_params(self) -> Dict[str, Any]:
        params = await super()._resolve_params()

        format         = await self.context.render_variable(self.config.format)
        cookies        = (await self.context.render_variable(self.config.cookies)) or []
        extractor_args = (await self.context.render_variable(self.config.extractor_args)) or {}
        js_runtimes    = (await self.context.render_variable(self.config.js_runtimes)) or []

        params.update({
            "format":         format,
            "cookies":        cookies,
            "extractor_args": extractor_args,
            "js_runtimes":    js_runtimes,
        })

        return params

    async def _download_batch(
        self,
        urls: List[str],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[DownloadResult]:
        return await asyncio.gather(*[
            self._download(url, params, cancellation_token) for url in urls
        ])

    async def _download(
        self,
        url: str,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> DownloadResult:
        # Reserve a unique path (no file created yet) and hand it to yt-dlp
        # via `outtmpl`. `.%(ext)s` lets yt-dlp pick the real extension
        # after resolving the format / postprocessor. Split the path so
        # `paths` can pin every intermediate artifact (.part fragments,
        # pre-merge streams) to the same temp dir; otherwise yt-dlp
        # writes some of them relative to cwd.
        output_template = get_temporary_path(extension="%(ext)s")
        output_dir = os.path.dirname(output_template)
        output_name = os.path.basename(output_template)

        format_options, is_audio = self._build_format_options(params["format"])
        js_runtimes_option = self._build_js_runtimes_option(params["js_runtimes"])
        cookiefile = self._create_cookies_file(params["cookies"]) if params["cookies"] else None

        options = self._build_ytdlp_options(
            output_dir=output_dir,
            output_name=output_name,
            format_options=format_options,
            cookiefile=cookiefile,
            extractor_args=params["extractor_args"],
            js_runtimes=js_runtimes_option,
        )

        logging.debug("Downloading '%s' via yt-dlp (format=%s)", url, params["format"])

        try:
            path = await asyncio.to_thread(self._run_ytdlp, url, options, cancellation_token)
        finally:
            if cookiefile is not None:
                try:
                    os.remove(cookiefile)
                except FileNotFoundError:
                    pass

        format_hint = get_file_extension(path)
        stream = FileStreamResource(path, auto_delete=True)

        if is_audio:
            return AudioStreamResource(stream, format=format_hint)

        return VideoStreamResource(stream, format=format_hint)

    @staticmethod
    def _build_format_options(format: Union[str, Dict[str, Any], None]) -> Tuple[Dict[str, Any], bool]:
        """Turn the DSL `format` value into yt-dlp options plus an audio/video flag.

        Accepts three shapes:
        - None: default best video+audio merge.
        - str: preset name (e.g. `mp3`, `mp4`) if in the preset whitelist, otherwise
          a raw yt-dlp `-f` expression passed through verbatim.
        - dict: structured `YtdlpFormatSpec` (already rendered to a plain dict);
          compiled to a `-f` selector plus optional postprocessors.

        Returns (options_fragment, is_audio) where `is_audio` decides whether the
        result should be wrapped as an AudioStreamResource.
        """
        if isinstance(format, dict):
            media = format.get("media")

            if media not in ("audio", "video"):
                raise ValueError(f"YtdlpFormatSpec.media must be 'audio' or 'video', got {media!r}")

            is_audio     = bool(media == "audio")
            container    = format.get("container")
            codec        = format.get("codec")
            max_bitrate  = format.get("max_bitrate")
            max_filesize = format.get("max_filesize")
            prefer_free  = format.get("prefer_free_formats")

            filters: List[str] = []

            if container:
                filters.append(f"ext={container}")

            if codec:
                filters.append(f"{'acodec' if is_audio else 'vcodec'}^={codec}")

            if max_bitrate is not None:
                filters.append(f"{'abr' if is_audio else 'vbr'}<={max_bitrate}")

            if max_filesize is not None:
                filters.append(f"filesize<={max_filesize}")

            if is_audio:
                selector = "bestaudio" + "".join(f"[{f}]" for f in filters) + "/bestaudio/best"
            else:
                max_height = format.get("max_height")
                max_fps    = format.get("max_fps")
                hdr        = format.get("hdr")

                video_filters = list(filters)

                if max_height is not None:
                    video_filters.append(f"height<={max_height}")

                if max_fps is not None:
                    video_filters.append(f"fps<={max_fps}")

                if hdr:
                    video_filters.append("dynamic_range=hdr")

                # Match yt-dlp's default merge shape (bestvideo+bestaudio/best) so
                # separate streams get combined when available.
                video_filter_str = "".join(f"[{f}]" for f in video_filters)
                audio_filter_str = "".join(f"[{f}]" for f in filters) if filters else ""
                selector = f"bestvideo{video_filter_str}+bestaudio{audio_filter_str}/best{video_filter_str}/best"

            options: Dict[str, Any] = { "format": selector }

            if prefer_free:
                options["prefer_free_formats"] = True

            if is_audio:
                options["postprocessors"] = [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": (container or "m4a"),
                }]
            elif container:
                options["merge_output_format"] = container

            return options, is_audio

        if isinstance(format, str):
            preset = _FORMAT_PRESETS.get(format)

            if preset is not None:
                return preset

            # Raw yt-dlp format expression — audio/video intent is opaque, so
            # default to video wrapping. Callers who want audio semantics should
            # use a preset or structured spec instead.
            return { "format": format }, False

        return { "format": "best" }, False

    @staticmethod
    def _build_js_runtimes_option(runtimes: Any) -> Dict[str, Dict[str, Any]]:
        """Accept the YAML-friendly shapes and return yt-dlp's {runtime: {config}} form.

        A bare string or a list of `RUNTIME[:PATH]` entries mirrors the
        `--js-runtimes` CLI spelling; a mapping is passed through so a caller
        can supply the full per-runtime config.
        """
        if not runtimes:
            return {}

        if isinstance(runtimes, dict):
            return { str(name): (config or {}) for name, config in runtimes.items() }

        if isinstance(runtimes, str):
            runtimes = [ runtimes ]

        option: Dict[str, Dict[str, Any]] = {}

        for runtime in runtimes:
            name, _, path = str(runtime).partition(":")
            option[name] = { "path": path or None }

        return option

    @staticmethod
    def _create_cookies_file(cookies: List[Dict[str, Any]]) -> str:
        path = get_temporary_path("txt")

        # Python's http.cookiejar refuses to load the file without this magic
        # header line, and yt-dlp defers to that loader.
        lines = [ "# Netscape HTTP Cookie File" ]

        for cookie in cookies:
            name  = cookie.get("name")
            value = cookie.get("value")

            if name is None or value is None:
                continue

            domain = str(cookie.get("domain") or "")

            # Netscape's include-subdomains flag is inferred from a leading dot
            # on the domain — CDP/Playwright follow the same convention.
            include_subdomains = "TRUE" if domain.startswith(".") else "FALSE"
            cookie_path = str(cookie.get("path") or "/")
            secure = "TRUE" if cookie.get("secure") else "FALSE"

            # CDP reports session cookies with expires=-1 and Playwright with
            # expires=-1 or expires=0; the Netscape format only accepts a
            # non-negative unix timestamp (0 means session cookie). Coerce
            # any negative or unparseable value to 0.
            try:
                expiry = int(float(cookie.get("expires", 0)))
            except (TypeError, ValueError):
                expiry = 0
            expiry_field = str(max(expiry, 0))

            # httpOnly cookies use the `#HttpOnly_` prefix on the domain per
            # curl/wget convention, which yt-dlp's loader recognizes.
            row_domain = f"#HttpOnly_{domain}" if cookie.get("httpOnly") else domain

            lines.append("\t".join([ row_domain, include_subdomains, cookie_path, secure, expiry_field, str(name), str(value) ]))

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

        return path

    @staticmethod
    def _build_ytdlp_options(
        output_dir: str,
        output_name: str,
        format_options: Dict[str, Any],
        cookiefile: Optional[str],
        extractor_args: Optional[Dict[str, Dict[str, Any]]] = None,
        js_runtimes: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        options: Dict[str, Any] = {
            "outtmpl":     output_name,
            # `home` receives the final file; `temp` catches .part fragments
            # and pre-merge streams so nothing lands in the process cwd.
            "paths":       { "home": output_dir, "temp": output_dir },
            "quiet":       True,
            "no_warnings": True,
            "noplaylist":  True,
            "remote_components": [ "ejs:github" ],
        }

        options.update(format_options)

        if cookiefile:
            options["cookiefile"] = cookiefile

        if extractor_args:
            options["extractor_args"] = extractor_args

        if js_runtimes:
            options["js_runtimes"] = js_runtimes

        return options

    @staticmethod
    def _run_ytdlp(
        url: str,
        options: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> str:
        from yt_dlp import YoutubeDL
        from yt_dlp.utils import DownloadError

        def _progress_hook(status: Dict[str, Any]) -> None:
            if cancellation_token is not None and cancellation_token.is_cancelled():
                # yt-dlp treats DownloadError raised from a progress hook as a
                # hard abort — the cleanest way to unblock a running download.
                raise DownloadError("cancelled")

        options = dict(options)
        options.setdefault("progress_hooks", []).append(_progress_hook)

        with YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)

        # `requested_downloads` reflects the final path after postprocessing
        # (e.g. audio extraction rewrites the extension). Fall back to
        # prepare_filename in case the field is missing on older yt-dlp versions.
        downloads = info.get("requested_downloads") if isinstance(info, dict) else None

        if downloads:
            path = downloads[0].get("filepath") or downloads[0].get("_filename")

            if path:
                return path

        with YoutubeDL(options) as ydl:
            return ydl.prepare_filename(info)

@register_media_downloader_service(MediaDownloaderDriver.YTDLP)
class YtdlpMediaDownloaderService(MediaDownloaderService):
    def __init__(self, id: str, config: MediaDownloaderComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "yt-dlp" ]

    async def _run(self, action: MediaDownloaderActionConfig, context: ComponentActionContext) -> Any:
        return await YtdlpMediaDownloaderAction(action, context).run()
