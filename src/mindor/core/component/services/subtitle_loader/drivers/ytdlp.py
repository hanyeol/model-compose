from __future__ import annotations

from typing import Union, Optional, Tuple, Dict, List, Any
from mindor.dsl.schema.component import SubtitleLoaderComponentConfig, SubtitleLoaderDriver
from mindor.dsl.schema.action import SubtitleLoaderActionConfig, YtdlpSubtitleLoaderActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.files import get_temporary_path, get_file_extension
from mindor.core.logger import logging
from ..base import SubtitleLoaderService, register_subtitle_loader_service
from ..base import ComponentActionContext
from .common import SubtitleLoaderAction
from ...media_downloader.drivers.ytdlp import YtdlpMediaDownloaderAction
import asyncio, os

class YtdlpSubtitleLoaderAction(SubtitleLoaderAction):
    async def _prepare_input(self) -> Any:
        return await self.context.render_variable(self.config.url)

    async def _resolve_params(self) -> Dict[str, Any]:
        params = await super()._resolve_params()

        languages              = await self.context.render_array(self.config.languages, single_as_array=True)
        format                 = await self.context.render_variable(self.config.format)
        include_auto_generated = await self.context.render_scalar(self.config.include_auto_generated, bool)
        cookies                = (await self.context.render_variable(self.config.cookies)) or []
        extractor_args         = (await self.context.render_variable(self.config.extractor_args)) or {}
        js_runtimes            = (await self.context.render_variable(self.config.js_runtimes)) or []

        if languages:
            languages = await languages.collect()

        params.update({
            "languages":              languages,
            "format":                 format,
            "include_auto_generated": include_auto_generated,
            "cookies":                cookies,
            "extractor_args":         extractor_args,
            "js_runtimes":            js_runtimes,
        })

        return params

    async def _load_batch(
        self,
        sources: List[str],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Union[Dict[str, Any], List[Dict[str, Any]]]]:
        return await asyncio.gather(*[
            self._load(url, params, cancellation_token) for url in sources
        ])

    async def _load(
        self,
        url: str,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Dict[str, Any]]:
        output_template = get_temporary_path(extension="%(ext)s")
        output_dir = os.path.dirname(output_template)
        output_name = os.path.basename(output_template)

        subtitle_format = params["format"] or "srt"
        languages = params["languages"] or [ "en" ]

        js_runtimes_option = self._build_js_runtimes_option(params["js_runtimes"])
        cookiefile = self._create_cookies_file(params["cookies"]) if params["cookies"] else None

        options = self._build_ytdlp_options(
            output_dir=output_dir,
            output_name=output_name,
            subtitle_format=subtitle_format,
            languages=languages,
            include_auto_generated=params["include_auto_generated"],
            cookiefile=cookiefile,
            extractor_args=params["extractor_args"],
            js_runtimes=js_runtimes_option,
        )

        logging.debug("Fetching subtitles for '%s' via yt-dlp (format=%s, languages=%s)", url, subtitle_format, languages)

        try:
            info = await asyncio.to_thread(self._run_ytdlp, url, options, cancellation_token)
        finally:
            if cookiefile is not None:
                try:
                    os.remove(cookiefile)
                except FileNotFoundError:
                    pass

        subtitle_files = self._collect_subtitle_files(info, output_dir, output_name, languages, subtitle_format)

        if not subtitle_files:
            raise RuntimeError(f"No subtitles available for '{url}' in languages {languages!r}")

        results: List[Dict[str, Any]] = []

        for subtitle_path, language, is_auto_generated in subtitle_files:
            try:
                result = await asyncio.to_thread(self._parse_subtitle_file, subtitle_path, subtitle_format)
            finally:
                try:
                    os.remove(subtitle_path)
                except FileNotFoundError:
                    pass

            result["language"] = language
            result["is_auto_generated"] = is_auto_generated
            results.append(result)

        return results

    @staticmethod
    def _build_ytdlp_options(
        output_dir: str,
        output_name: str,
        subtitle_format: str,
        languages: List[str],
        include_auto_generated: bool,
        cookiefile: Optional[str],
        extractor_args: Optional[Dict[str, Dict[str, Any]]] = None,
        js_runtimes: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        options: Dict[str, Any] = {
            "outtmpl": output_name,
            "paths": { "home": output_dir, "temp": output_dir },
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "skip_download": True,
            "writesubtitles": True,
            "writeautomaticsub": bool(include_auto_generated),
            "subtitleslangs": languages,
            "subtitlesformat": subtitle_format,
            "remote_components": [ "ejs:github" ],
        }

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
    ) -> Dict[str, Any]:
        from yt_dlp import YoutubeDL
        from yt_dlp.utils import DownloadError

        def _progress_hook(status: Dict[str, Any]) -> None:
            if cancellation_token is not None and cancellation_token.is_cancelled():
                raise DownloadError("cancelled")

        options = dict(options)
        options.setdefault("progress_hooks", []).append(_progress_hook)

        with YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)

        return info if isinstance(info, dict) else {}

    @staticmethod
    def _collect_subtitle_files(
        info: Dict[str, Any],
        output_dir: str,
        output_name: str,
        languages: List[str],
        subtitle_format: str,
    ) -> List[Tuple[str, str, bool]]:
        """Locate every downloaded subtitle file for the requested languages.

        yt-dlp writes subtitles to `<outtmpl>.<lang>.<ext>` alongside the
        (skipped) media file. We keep the caller-supplied language order so
        priority-sensitive consumers can trust the sequence, and flag each
        entry as auto-generated when yt-dlp only exposed it via
        `automatic_captions`.
        """
        base_name, _, _ = output_name.partition(".")
        base_path = os.path.join(output_dir, base_name)

        human_subs    = (info.get("subtitles") or {}) if isinstance(info, dict) else {}
        auto_captions = (info.get("automatic_captions") or {}) if isinstance(info, dict) else {}

        results: List[Tuple[str, str, bool]] = []
        for language in languages:
            candidate = f"{base_path}.{language}.{subtitle_format}"
            if os.path.exists(candidate):
                is_auto = language in auto_captions and language not in human_subs
                results.append((candidate, language, is_auto))

        return results

    @staticmethod
    def _parse_subtitle_file(path: str, format: Optional[str]) -> Dict[str, Any]:
        import pysubs2

        # yt-dlp always re-writes subtitles as UTF-8, but some extractors emit
        # a UTF-8 BOM. Use `utf-8-sig` to strip the BOM when present so it does
        # not leak into the first segment's text; harmless when absent.
        load_params: Dict[str, Any] = { "encoding": "utf-8-sig" }

        if format:
            load_params["format_"] = format

        subtitles = pysubs2.load(path, **load_params)
        segments: List[Dict[str, Any]] = []

        for event in subtitles.events:
            if event.type != "Dialogue":
                continue

            start_time = event.start / 1000.0
            end_time   = event.end / 1000.0

            segments.append({
                "text":       event.plaintext,
                "start_time": start_time,
                "end_time":   end_time,
                "duration":   end_time - start_time,
            })

        full_text = " ".join(segment["text"] for segment in segments)

        return {
            "segments":  segments,
            "full_text": full_text,
            "format":    subtitles.format,
        }

@register_subtitle_loader_service(SubtitleLoaderDriver.YTDLP)
class YtdlpSubtitleLoaderService(SubtitleLoaderService):
    def __init__(self, id: str, config: SubtitleLoaderComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "yt-dlp", "pysubs2" ]

    async def _run(self, action: SubtitleLoaderActionConfig, context: ComponentActionContext) -> Any:
        return await YtdlpSubtitleLoaderAction(action, context).run()
