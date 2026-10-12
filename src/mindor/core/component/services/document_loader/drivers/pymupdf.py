from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Optional, Dict, List, Tuple, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import DocumentLoaderComponentConfig, DocumentLoaderDriverType
from mindor.dsl.schema.action import DocumentLoaderActionConfig, PymupdfDocumentLoaderActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from ..base import DocumentLoaderDriver, register_document_loader_driver
from ..base import ComponentActionContext
from .common import DocumentLoaderAction
import asyncio, os

if TYPE_CHECKING:
    from fitz import Document, Page

class PymupdfDocumentLoaderAction(DocumentLoaderAction):
    config: PymupdfDocumentLoaderActionConfig

    async def _resolve_params(self) -> Dict[str, Any]:
        params = await super()._resolve_params()

        password        = await self.context.render_variable(self.config.password)
        extraction_mode = await self.context.render_variable(self.config.extraction_mode)
        page_range      = await self.context.render_variable(self.config.page_range)

        params.update({
            "password":        password,
            "extraction_mode": extraction_mode or "text",
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
                doc = self._open_pdf(path, params)

                try:
                    if params["page_range"]:
                        page_indices = self._resolve_page_indices(params["page_range"], len(doc))
                    else:
                        page_indices = list(range(len(doc)))
                    pages: List[Dict[str, Any]] = []

                    for page_index in page_indices:
                        pages.append(self._extract_page(doc, page_index, params))

                    return { "pages": pages }
                finally:
                    doc.close()

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
            doc = await asyncio.to_thread(self._open_pdf, path, params)

            try:
                if params["page_range"]:
                    page_indices = self._resolve_page_indices(params["page_range"], len(doc))
                else:
                    page_indices = list(range(len(doc)))

                for page_index in page_indices:
                    if cancellation_token is not None and cancellation_token.is_cancelled():
                        break

                    yield await asyncio.to_thread(self._extract_page, doc, page_index, params)
            finally:
                doc.close()
        finally:
            if spooled:
                try:
                    os.remove(path)
                except FileNotFoundError:
                    pass

    @staticmethod
    def _open_pdf(path: str, params: Dict[str, Any]) -> Any:
        import fitz

        doc = fitz.open(path)

        if params.get("password") and doc.is_encrypted:
            authenticated = doc.authenticate(params["password"])

            if not authenticated:
                doc.close()
                raise ValueError(f"Failed to decrypt PDF document with provided password: {path}")

        return doc

    def _extract_page(
        self,
        doc: Document,
        page_index: int,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        page = doc[page_index]
        content = self._extract_page_content(page, params.get("extraction_mode") or "text")

        return {
            "text":    content if isinstance(content, str) else str(content),
            "content": content,
            "index":   page_index,
            "metadata": {
                "number":   page_index + 1,
                "rotation": page.rotation,
                "width":    float(page.rect.width),
                "height":   float(page.rect.height),
            },
        }

    @staticmethod
    def _extract_page_content(page: Page, mode: str) -> Union[str, List[Tuple[float, float, float, float, str, int, int]]]:
        if mode == "blocks":
            return page.get_text("blocks")

        if mode == "html":
            return page.get_text("html")

        if mode == "json":
            return page.get_text("json")

        return page.get_text("text") or ""

    @staticmethod
    def _resolve_page_indices(page_range: str, total_page_count: int) -> List[int]:
        indices: List[int] = []

        for part in page_range.split(","):
            part = part.strip()

            if not part:
                continue

            if "-" in part:
                start_str, end_str = part.split("-", 1)
                start = max(int(start_str), 1)
                end   = min(int(end_str), total_page_count)

                for page_number in range(start, end + 1):
                    indices.append(page_number - 1)
            else:
                page_number = int(part)

                if 1 <= page_number <= total_page_count:
                    indices.append(page_number - 1)

        return indices

@register_document_loader_driver(DocumentLoaderDriverType.PYMUPDF)
class PymupdfDocumentLoaderService(DocumentLoaderDriver):
    def __init__(self, id: str, config: DocumentLoaderComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return [ "pymupdf" ]

    async def _run(self, action: DocumentLoaderActionConfig, context: ComponentActionContext) -> Any:
        return await PymupdfDocumentLoaderAction(action, context).run()
