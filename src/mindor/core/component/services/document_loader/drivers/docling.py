from __future__ import annotations

from typing import TYPE_CHECKING, Union, Optional, Tuple, Dict, List, Iterator, Any
from collections.abc import AsyncIterator
from pydantic import BaseModel
from mindor.dsl.schema.component import (
    DocumentLoaderComponentConfig,
    DoclingDocumentLoaderComponentConfig,
    DocumentLoaderDriver,
)
from mindor.dsl.schema.action import DocumentLoaderActionConfig, DoclingDocumentLoaderActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from ..base import DocumentLoaderService, register_document_loader_service
from ..base import ComponentActionContext
from .common import DocumentLoaderAction
import asyncio, os

if TYPE_CHECKING:
    from transformers import PreTrainedTokenizerBase

class DoclingWholeDocumentChunker:
    """Fallback chunker that yields the entire document as a single chunk.

    Used when the user leaves ``chunker`` unset — the docling document is
    surfaced verbatim (markdown-exported) so downstream jobs can consume the
    parsed text without any segmentation.
    """
    def chunk(self, dl_doc: Any) -> Iterator[Any]:
        text = dl_doc.export_to_markdown() if hasattr(dl_doc, "export_to_markdown") else str(dl_doc)

        yield DoclingWholeDocumentChunk(text=text)

    def contextualize(self, chunk: Any) -> str:
        return chunk.text

class DoclingWholeDocumentChunk:
    def __init__(self, text: str):
        self.text: str = text
        self.meta = None

class DoclingDocumentLoaderAction(DocumentLoaderAction):
    config: DoclingDocumentLoaderActionConfig

    def __init__(
        self,
        config: DoclingDocumentLoaderActionConfig,
        context: ComponentActionContext,
        converter: Any,
        tokenizer: Optional[PreTrainedTokenizerBase],
    ):
        super().__init__(config, context)

        self._converter: Any = converter
        self._tokenizer: Optional[PreTrainedTokenizerBase] = tokenizer

    async def _resolve_params(self) -> Dict[str, Any]:
        params = await super()._resolve_params()

        chunker                 = await self.context.render_variable(self.config.chunker)
        max_token_count         = await self.context.render_variable(self.config.max_token_count)
        merge_peers             = await self.context.render_variable(self.config.merge_peers)
        repeat_table_header     = await self.context.render_variable(self.config.repeat_table_header)
        omit_header_on_overflow = await self.context.render_variable(self.config.omit_header_on_overflow)
        always_emit_headings    = await self.context.render_variable(self.config.always_emit_headings)
        code_chunking_strategy  = await self.context.render_variable(self.config.code_chunking_strategy)
        max_line_count          = await self.context.render_variable(self.config.max_line_count)
        return_enriched_text    = await self.context.render_variable(self.config.return_enriched_text)

        params.update({
            "chunker":                 chunker,
            "max_token_count":         max_token_count,
            "merge_peers":             merge_peers,
            "repeat_table_header":     repeat_table_header,
            "omit_header_on_overflow": omit_header_on_overflow,
            "always_emit_headings":    always_emit_headings,
            "code_chunking_strategy":  code_chunking_strategy,
            "max_line_count":          max_line_count,
            "return_enriched_text":    return_enriched_text,
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
            def _collect_chunks() -> Dict[str, Any]:
                doc = self._convert_document(path)
                chunker = self._build_chunker(params)
                chunks: List[Dict[str, Any]] = []

                for index, chunk in enumerate(chunker.chunk(dl_doc=doc)):
                    chunks.append(self._build_chunk_result(chunk, chunker, index, params))

                return { "chunks": chunks }

            return await self._run_in_executor(_collect_chunks)
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
            def _stream_chunk_iterator() -> Tuple[Any, Iterator[Any]]:
                doc = self._convert_document(path)
                chunker = self._build_chunker(params)

                return chunker, iter(chunker.chunk(dl_doc=doc))

            chunker, chunk_iterator = await self._run_in_executor(_stream_chunk_iterator)

            index = 0
            end_of_stream = object()

            while True:
                if cancellation_token is not None and cancellation_token.is_cancelled():
                    break

                def _next_chunk() -> Any:
                    return next(chunk_iterator, end_of_stream)

                chunk = await self._run_in_executor(_next_chunk)

                if chunk is end_of_stream:
                    break

                yield self._build_chunk_result(chunk, chunker, index, params)
                index += 1
        finally:
            if spooled:
                try:
                    os.remove(path)
                except FileNotFoundError:
                    pass

    def _convert_document(self, path_or_url: str) -> Any:
        """Parse a source path or URL into a docling ``DLDocument``.

        Runs synchronously and is intended to be invoked from an executor
        thread by the caller.
        """
        return self._converter.convert(source=path_or_url).document

    def _build_chunker(self, params: Dict[str, Any]) -> Any:
        """Instantiate the docling chunker selected by ``params['chunker']``.

        A new chunker is returned per action so per-action parameters
        (``max_token_count``, ``merge_peers``, etc.) take effect without
        mutating shared state.
        """
        chunker_name = params["chunker"]

        if chunker_name is None:
            return DoclingWholeDocumentChunker()

        if chunker_name == "hybrid":
            return self._build_hybrid_chunker(params)

        if chunker_name == "hierarchical":
            return self._build_hierarchical_chunker(params)

        if chunker_name == "line":
            return self._build_line_chunker(params)

        if chunker_name == "page":
            return self._build_page_chunker(params)

        raise ValueError(f"Unsupported docling chunker: {chunker_name}")

    def _build_hybrid_chunker(self, params: Dict[str, Any]) -> Any:
        from docling.chunking import HybridChunker

        chunker_params: Dict[str, Any] = {
            "merge_peers":             bool(params["merge_peers"]),
            "repeat_table_header":     bool(params["repeat_table_header"]),
            "omit_header_on_overflow": bool(params["omit_header_on_overflow"]),
        }

        if self._tokenizer is not None:
            chunker_params["tokenizer"] = self._resolve_tokenizer(self._tokenizer, params)

        return HybridChunker(**chunker_params)

    def _build_hierarchical_chunker(self, params: Dict[str, Any]) -> Any:
        from docling_core.transforms.chunker.hierarchical_chunker import HierarchicalChunker

        chunker_params: Dict[str, Any] = {
            "always_emit_headings": bool(params["always_emit_headings"]),
        }

        if params["code_chunking_strategy"] is not None:
            chunker_params["code_chunking_strategy"] = self._resolve_code_chunking_strategy(params["code_chunking_strategy"])

        return HierarchicalChunker(**chunker_params)

    def _build_line_chunker(self, params: Dict[str, Any]) -> Any:
        from docling_core.transforms.chunker.line_chunker import LineBasedTokenChunker

        chunker_params: Dict[str, Any] = {}

        if self._tokenizer is not None:
            chunker_params["tokenizer"] = self._resolve_tokenizer(self._tokenizer, params)

        if params["max_line_count"] is not None:
            chunker_params["lines_per_chunk"] = int(params["max_line_count"])

        return LineBasedTokenChunker(**chunker_params)

    def _build_page_chunker(self, params: Dict[str, Any]) -> Any:
        from docling_core.transforms.chunker.page_chunker import PageChunker

        return PageChunker()

    def _resolve_code_chunking_strategy(self, name: str) -> Any:
        """Instantiate the docling code chunking strategy for ``name``.

        Docling accepts a ``BaseCodeChunkingStrategy`` instance rather than a
        string, so we map the DSL literal onto the concrete class here.
        """
        if name == "standard":
            from docling_core.transforms.chunker.code_chunking.standard_code_chunking_strategy import StandardCodeChunkingStrategy

            return StandardCodeChunkingStrategy()

        raise ValueError(f"Unsupported docling code chunking strategy: {name}")

    def _resolve_tokenizer(self, tokenizer: PreTrainedTokenizerBase, params: Dict[str, Any]) -> Any:
        """Wrap ``tokenizer`` with the action's ``max_token_count``.

        The underlying tokenizer is loaded once by the service and reused
        across actions; a new ``HuggingFaceTokenizer`` wrapper is created per
        action so ``max_tokens`` can vary while the underlying model stays
        shared.
        """
        from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer

        tokenizer_params: Dict[str, Any] = { "tokenizer": tokenizer }

        if params["max_token_count"] is not None:
            tokenizer_params["max_tokens"] = int(params["max_token_count"])

        return HuggingFaceTokenizer(**tokenizer_params)

    def _build_chunk_result(
        self,
        chunk: Any,
        chunker: Any,
        index: int,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        meta: Dict[str, Any] = {}

        # DocChunk.meta is a Pydantic model with `export_json_dict()` returning
        # alias-keyed dicts (headings, doc_items, origin); fall back to a plain
        # dump for chunkers that emit non-DocChunk instances.
        chunk_meta = getattr(chunk, "meta", None)

        if chunk_meta is not None:
            if hasattr(chunk_meta, "export_json_dict"):
                meta = chunk_meta.export_json_dict()
            elif isinstance(chunk_meta, BaseModel):
                meta = chunk_meta.model_dump()

        result: Dict[str, Any] = {
            "text":  chunk.text,
            "index": index,
            "meta":  meta,
        }

        if params["return_enriched_text"]:
            result["enriched_text"] = chunker.contextualize(chunk=chunk)

        return result

@register_document_loader_service(DocumentLoaderDriver.DOCLING)
class DoclingDocumentLoaderService(DocumentLoaderService):
    def __init__(self, id: str, config: DoclingDocumentLoaderComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self._converter: Optional[Any] = None
        self._tokenizer: Optional[PreTrainedTokenizerBase] = None

    def _get_setup_requirements(self) -> Optional[List[str]]:
        requirements = [ "docling", "docling-core>=2.67.0" ]

        if self.config.tokenizer:
            requirements.append("transformers")

        return requirements

    async def _start(self) -> None:
        await super()._start()

        self._converter = await asyncio.to_thread(self._load_document_converter)

        if self.config.tokenizer:
            self._tokenizer = await asyncio.to_thread(self._load_pretrained_tokenizer, self.config.tokenizer)

    async def _stop(self) -> None:
        self._converter = None
        self._tokenizer = None

        await super()._stop()

    async def _run(self, action: DocumentLoaderActionConfig, context: ComponentActionContext) -> Any:
        return await DoclingDocumentLoaderAction(action, context, self._converter, self._tokenizer).run()

    def _load_document_converter(self) -> Any:
        from docling.document_converter import DocumentConverter

        # The DocumentConverter constructor accepts pipeline options via
        # `format_options`; we keep the default pipeline for now and rely on
        # docling's own defaults. Component-level fields (ocr, table_mode,
        # accelerator) become plumbing here as their downstream wiring solidifies.
        return DocumentConverter()

    @staticmethod
    def _load_pretrained_tokenizer(tokenizer_id: str) -> PreTrainedTokenizerBase:
        from transformers import AutoTokenizer

        return AutoTokenizer.from_pretrained(tokenizer_id)
