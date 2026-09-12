from typing import Literal, Optional, List
from pydantic import Field
from mindor.dsl.schema.action import DoclingDocumentLoaderActionConfig
from .common import CommonDocumentLoaderComponentConfig, DocumentLoaderDriver

class DoclingDocumentLoaderComponentConfig(CommonDocumentLoaderComponentConfig):
    driver: Literal[DocumentLoaderDriver.DOCLING]
    backend: Optional[Literal[ "pypdfium2" ]] = Field(default=None, description="Override the PDF backend used by docling; 'pypdfium2' is faster on text-layer PDFs but skips OCR.")
    enable_ocr: bool = Field(default=False, description="Whether to run OCR on scanned or image-based pages.")
    ocr_engine: Optional[Literal[ "easyocr", "tesseract", "rapidocr", "ocrmac" ]] = Field(default=None, description="OCR engine identifier; docling default (easyocr) is used when omitted.")
    recognize_table: bool = Field(default=True, description="Whether to run table structure recognition.")
    table_mode: Optional[Literal[ "fast", "accurate" ]] = Field(default=None, description="Table structure recognition mode; 'fast' trades accuracy for speed.")
    accelerator: Optional[Literal[ "auto", "cpu", "cuda", "mps" ]] = Field(default=None, description="Accelerator device for model inference; 'auto' lets docling choose.")
    tokenizer: Optional[str] = Field(default=None, description="HuggingFace tokenizer id used by token-aware chunkers (e.g. hybrid); loaded once and shared across actions.")
    actions: List[DoclingDocumentLoaderActionConfig] = Field(default_factory=list)
