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
from mindor.core.logger import logging
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
        # docling-slim is the actual package shipping the docling Python
        # modules from v2.100.0 onward; the legacy `docling` distribution
        # became a CLI-only alias whose install can leave the top-level
        # docling package files missing. Pinning docling-slim directly avoids
        # that broken half-install.
        #
        # Extras are assembled per component config so only the pipeline
        # pieces this instance actually uses get downloaded:
        #   feat-chunking       — always required (docling-core[chunking]
        #                         provides LineBasedTokenChunker and the
        #                         tree-sitter/transformers deps the chunker
        #                         package imports eagerly).
        #   format-pdf-docling  — always required. docling-slim's
        #                         document_converter imports docling-parse
        #                         unconditionally, so even when the action
        #                         uses `backend: pypdfium2` docling-parse
        #                         must be installed for the base module to
        #                         load. This extra bundles pypdfium2 too, so
        #                         a separate format-pdf-pypdfium2 pin is
        #                         redundant.
        #   models-local        — always required. The standard PDF pipeline
        #                         loads docling-ibm-models (layout, reading
        #                         order, TableFormer) at construction time,
        #                         regardless of `recognize_table`.
        #   feat-ocr-<engine>   — OCR engine when `enable_ocr` is set.
        extras: List[str] = [ "feat-chunking", "format-pdf-docling", "models-local" ]

        if self.config.enable_ocr:
            engine = self.config.ocr_engine or "easyocr"
            extras.append(f"feat-ocr-{engine}")

        return [ f"docling-slim[{','.join(extras)}]>=2.100.0" ]

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
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions

        # PyPdfiumDocumentBackend reads only the PDF text layer and ignores
        # `do_ocr` entirely, so pairing it with `enable_ocr: true` is a silent
        # no-op. Warn but keep going — scanned PDFs will just come back empty,
        # which is the documented behavior of that backend.
        if self.config.backend == "pypdfium2" and self.config.enable_ocr:
            logging.warning(
                "docling `backend: pypdfium2` does not run OCR; `enable_ocr: true` is ignored for component '%s'.",
                self.id,
            )

        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = self.config.enable_ocr
        pipeline_options.do_table_structure = self.config.recognize_table

        if self.config.enable_ocr and self.config.ocr_engine:
            pipeline_options.ocr_options = self._build_ocr_options(self.config.ocr_engine)

        if self.config.recognize_table and self.config.table_mode:
            from docling.datamodel.pipeline_options import TableFormerMode

            pipeline_options.table_structure_options.mode = TableFormerMode(self.config.table_mode)

        if self.config.accelerator:
            from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions

            pipeline_options.accelerator_options = AcceleratorOptions(
                device=AcceleratorDevice(self.config.accelerator),
            )

        pdf_format_option = PdfFormatOption(pipeline_options=pipeline_options)

        if self.config.backend == "pypdfium2":
            from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend

            pdf_format_option = PdfFormatOption(pipeline_options=pipeline_options, backend=PyPdfiumDocumentBackend)

        return DocumentConverter(format_options={ InputFormat.PDF: pdf_format_option })

    @staticmethod
    def _build_ocr_options(engine: str) -> Any:
        """Instantiate docling's OCR options for the requested engine.

        Docling ships engine-specific option classes (EasyOcrOptions,
        TesseractOcrOptions, RapidOcrOptions, OcrMacOptions). Unknown engine
        names raise a clear error rather than silently falling back to the
        default engine.
        """
        if engine == "easyocr":
            from docling.datamodel.pipeline_options import EasyOcrOptions

            return EasyOcrOptions()

        if engine == "tesseract":
            from docling.datamodel.pipeline_options import TesseractOcrOptions

            return TesseractOcrOptions()

        if engine == "rapidocr":
            from docling.datamodel.pipeline_options import RapidOcrOptions

            return RapidOcrOptions()

        if engine == "ocrmac":
            from docling.datamodel.pipeline_options import OcrMacOptions

            return OcrMacOptions()

        raise ValueError(f"Unsupported docling OCR engine: {engine}")

    @staticmethod
    def _load_pretrained_tokenizer(tokenizer_id: str) -> PreTrainedTokenizerBase:
        from transformers import AutoTokenizer

        return AutoTokenizer.from_pretrained(tokenizer_id)
