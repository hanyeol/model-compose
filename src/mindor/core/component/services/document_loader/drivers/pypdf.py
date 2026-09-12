from __future__ import annotations

from typing import Union, Optional, Dict, List, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import DocumentLoaderComponentConfig, DocumentLoaderDriver
from mindor.dsl.schema.action import DocumentLoaderActionConfig, PypdfDocumentLoaderActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from ..base import DocumentLoaderService, register_document_loader_service
from ..base import ComponentActionContext
from .common import DocumentLoaderAction
import asyncio, os

class PypdfDocumentLoaderAction(DocumentLoaderAction):
    config: PypdfDocumentLoaderActionConfig

    async def _resolve_params(self) -> Dict[str, Any]:
        params = await super()._resolve_params()

        password        = await self.context.render_variable(self.config.password)
        extraction_mode = await self.context.render_variable(self.config.extraction_mode)
        page_range      = await self.context.render_variable(self.config.page_range)

        params.update({
            "password":        password,
            "extraction_mode": extraction_mode,
            "page_range":      page_range,
        })

        return params

    async def _load_batch(
        self,
        sources: List[Any],
        params: Dict[str, Any],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Union[Dict[str, Any], AsyncIterator[Dict[str, Any]]]]:
        if streaming:
            return [ self._stream_document(source, params, cancellation_token) for source in sources ]

        return await asyncio.gather(*[
            self._load_document(source, params, cancellation_token) for source in sources
        ])

    async def _load_document(
        self,
        source: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        path, spooled = await self._resolve_source_path(source, ".pdf")

        try:
            def _collect_pages() -> Dict[str, Any]:
                reader = self._create_pdf_reader(path, params)
                page_indices = self._resolve_page_indices(params["page_range"], len(reader.pages))
                pages: List[Dict[str, Any]] = []

                for page_index in page_indices:
                    pages.append(self._extract_page(reader, page_index, params))

                return { "pages": pages }

            return await asyncio.to_thread(_collect_pages)
        finally:
            if spooled:
                try:
                    os.remove(path)
                except FileNotFoundError:
                    pass

    async def _stream_document(
        self,
        source: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        path, spooled = await self._resolve_source_path(source, ".pdf")

        try:
            reader = await asyncio.to_thread(self._create_pdf_reader, path, params)
            page_indices = self._resolve_page_indices(params["page_range"], len(reader.pages))

            for page_index in page_indices:
                if cancellation_token is not None and cancellation_token.is_cancelled():
                    break

                yield await asyncio.to_thread(self._extract_page, reader, page_index, params)
        finally:
            if spooled:
                try:
                    os.remove(path)
                except FileNotFoundError:
                    pass

    @staticmethod
    def _create_pdf_reader(path: str, params: Dict[str, Any]) -> Any:
        from pypdf import PdfReader

        reader = PdfReader(path)

        if params["password"]:
            reader.decrypt(params["password"])

        return reader

    @staticmethod
    def _extract_page(
        reader: Any,
        page_index: int,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        page = reader.pages[page_index]
        text = page.extract_text(extraction_mode=params["extraction_mode"]) or ""

        return {
            "text":  text,
            "index": page_index,
            "meta":  {
                "number":   page_index + 1,
                "rotation": page.rotation,
            },
        }

    @staticmethod
    def _resolve_page_indices(page_range: Optional[str], total_pages: int) -> List[int]:
        """Parse ``page_range`` strings like ``"1-5,7"`` into zero-based indices.

        Page numbers in the range spec are one-based (matching PDF viewer
        conventions). Returns all page indices in order when ``page_range`` is
        empty.
        """
        if not page_range:
            return list(range(total_pages))

        indices: List[int] = []

        for part in page_range.split(","):
            part = part.strip()

            if not part:
                continue

            if "-" in part:
                start_str, end_str = part.split("-", 1)
                start = max(int(start_str), 1)
                end   = min(int(end_str), total_pages)

                for page_number in range(start, end + 1):
                    indices.append(page_number - 1)
            else:
                page_number = int(part)

                if 1 <= page_number <= total_pages:
                    indices.append(page_number - 1)

        return indices

@register_document_loader_service(DocumentLoaderDriver.PYPDF)
class PypdfDocumentLoaderService(DocumentLoaderService):
    def __init__(self, id: str, config: DocumentLoaderComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return [ "pypdf" ]

    async def _run(self, action: DocumentLoaderActionConfig, context: ComponentActionContext) -> Any:
        return await PypdfDocumentLoaderAction(action, context).run()
