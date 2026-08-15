from __future__ import annotations

from typing import Optional, Dict, List, Any
from urllib.parse import urlparse
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

class YtdlpMediaDownloaderAction(MediaDownloaderAction):
    async def _resolve_params(self) -> Dict[str, Any]:
        params = await super()._resolve_params()

        format_selector = await self.context.render_scalar(self.config.format_selector, str)
        extract_audio   = await self.context.render_scalar(self.config.extract_audio, bool, False)
        video_format    = await self.context.render_scalar(self.config.video_format, str)
        audio_format    = await self.context.render_scalar(self.config.audio_format, str)
        cookies         = (await self.context.render_variable(self.config.cookies)) or {}

        params.update({
            "format_selector": format_selector,
            "extract_audio":   extract_audio,
            "video_format":    video_format,
            "audio_format":    audio_format,
            "cookies":         cookies,
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
        # after resolving the format / postprocessor.
        output_template = get_temporary_path(extension="%(ext)s")

        # yt-dlp only accepts a Netscape-format cookies file, not a plain
        # dict. Materialize the rendered dict into a temp file when non-empty
        # and clean it up after the download completes.
        cookiefile = self._create_cookies_file(params["cookies"], url) if params["cookies"] else None

        options = self._build_options(
            output_template=output_template,
            format_selector=params["format_selector"],
            extract_audio=params["extract_audio"],
            audio_format=params["audio_format"],
            video_format=params["video_format"],
            cookiefile=cookiefile,
        )

        logging.debug("Downloading '%s' via yt-dlp (extract_audio=%s)", url, params["extract_audio"])

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

        if params["extract_audio"]:
            return AudioStreamResource(stream, format=format_hint)

        return VideoStreamResource(stream, format=format_hint)

    @staticmethod
    def _create_cookies_file(cookies: Dict[str, str], url: str) -> str:
        domain = urlparse(url).hostname or ""
        domain_field = ("." + domain) if domain and not domain.startswith(".") else domain

        path = get_temporary_path("txt")
        lines = []

        for name, value in cookies.items():
            # domain, include_subdomains, path, secure, expiry, name, value
            lines.append("\t".join([ domain_field, "TRUE", "/", "FALSE", "0", str(name), str(value) ]))

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

        return path

    @staticmethod
    def _build_options(
        output_template: str,
        format_selector: Optional[str],
        extract_audio: bool,
        audio_format: Optional[str],
        video_format: Optional[str],
        cookiefile: Optional[str],
    ) -> Dict[str, Any]:
        options: Dict[str, Any] = {
            "outtmpl":     output_template,
            "quiet":       True,
            "no_warnings": True,
            "noplaylist":  True,
        }

        if format_selector:
            options["format"] = format_selector
        elif extract_audio:
            options["format"] = "bestaudio/best"
        elif video_format:
            # Prefer a merged stream in the requested container; fall back to best.
            options["format"] = f"bestvideo[ext={video_format}]+bestaudio/best[ext={video_format}]/best"
            options["merge_output_format"] = video_format
        else:
            options["format"] = "best"

        if extract_audio:
            options["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": (audio_format or "m4a"),
            }]

        if cookiefile:
            options["cookiefile"] = cookiefile

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
        requested = info.get("requested_downloads") if isinstance(info, dict) else None
        if requested:
            path = requested[0].get("filepath") or requested[0].get("_filename")
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
