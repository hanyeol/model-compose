from __future__ import annotations

from typing import Optional, Tuple, Dict, List, Any
from mindor.dsl.schema.component import SubtitleLoaderComponentConfig, SubtitleLoaderDriver
from mindor.dsl.schema.action import SubtitleLoaderActionConfig, LocalSubtitleLoaderActionConfig
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.foundation.streaming.resources import save_stream_to_temporary_file
from mindor.core.foundation.streaming.resolver import resolve_stream_resource
from mindor.core.foundation.cancellation import CancellationToken
from ..base import SubtitleLoaderService, register_subtitle_loader_service
from ..base import ComponentActionContext
from .common import SubtitleLoaderAction
import asyncio, os

class LocalSubtitleLoaderAction(SubtitleLoaderAction):
    async def _prepare_input(self) -> Any:
        return await self.context.render_variable(self.config.source)

    async def _resolve_params(self) -> Dict[str, Any]:
        params = await super()._resolve_params()

        format   = await self.context.render_variable(self.config.format)
        encoding = await self.context.render_variable(self.config.encoding)

        params.update({
            "format":   format,
            "encoding": encoding,
        })

        return params

    async def _load_batch(
        self,
        sources: List[Any],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Dict[str, Any]]:
        return await asyncio.gather(*[
            self._load(source, params, cancellation_token) for source in sources
        ])

    async def _load(
        self,
        source: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        path, spooled = await self._resolve_source_path(source, params["format"])

        try:
            result = await asyncio.to_thread(self._parse_subtitle_file, path, params["format"], params["encoding"])
        finally:
            if spooled:
                try:
                    os.remove(path)
                except FileNotFoundError:
                    pass

        return result

    async def _resolve_source_path(self, source: Any, format: Optional[str]) -> Tuple[str, bool]:
        """Turn any accepted source shape into a filesystem path pysubs2 can read.

        Returns ``(path, spooled)``. When ``spooled`` is True the caller must
        remove ``path`` after use. Mirrors ``MediaInputPathResolver.resolve``.

        pysubs2 sniffs the file contents to detect the format regardless of
        extension, so the spool file's extension is informational only — the
        caller's ``format`` hint is used when available, otherwise the temp
        file is left without an extension and pysubs2 falls back to content
        sniffing during parsing.
        """
        if isinstance(source, str) and os.path.exists(source):
            return source, False

        stream = await resolve_stream_resource(source)

        if isinstance(stream, FileStreamResource):
            return stream.path, False

        spooled_path = await save_stream_to_temporary_file(stream, format)

        return spooled_path, True

    @staticmethod
    def _parse_subtitle_file(path: str, format: Optional[str], encoding: Optional[str]) -> Dict[str, Any]:
        import pysubs2

        load_params: Dict[str, Any] = {}

        if encoding is not None:
            load_params["encoding"] = encoding

        if format:
            load_params["format_"] = format

        subtitles = pysubs2.load(path, **load_params)
        segments: List[Dict[str, Any]] = []

        for event in subtitles.events:
            # SSA/ASS allows non-dialogue lines (Comment/Picture/Sound/etc.);
            # only Dialogue events represent spoken captions we want to surface.
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

@register_subtitle_loader_service(SubtitleLoaderDriver.LOCAL)
class LocalSubtitleLoaderService(SubtitleLoaderService):
    def __init__(self, id: str, config: SubtitleLoaderComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "pysubs2" ]

    async def _run(self, action: SubtitleLoaderActionConfig, context: ComponentActionContext) -> Any:
        return await LocalSubtitleLoaderAction(action, context).run()
