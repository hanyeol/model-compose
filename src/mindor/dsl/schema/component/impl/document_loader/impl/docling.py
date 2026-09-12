from typing import Literal, Optional, List
from pydantic import Field
from mindor.dsl.schema.action import DoclingDocumentLoaderActionConfig
from .common import CommonDocumentLoaderComponentConfig, DocumentLoaderDriver

class DoclingDocumentLoaderComponentConfig(CommonDocumentLoaderComponentConfig):
    driver: Literal[DocumentLoaderDriver.DOCLING]
    ocr: bool = Field(default=False, description="Whether to run OCR on scanned or image-based pages.")
    ocr_engine: Optional[str] = Field(default=None, description="OCR engine identifier (e.g. 'easyocr', 'tesseract'); driver default used when omitted.")
    table_mode: Optional[str] = Field(default=None, description="Table structure recognition mode (e.g. 'fast', 'accurate').")
    do_table_structure: bool = Field(default=True, description="Whether to run table structure recognition.")
    accelerator: Optional[str] = Field(default=None, description="Accelerator device for model inference (e.g. 'cpu', 'cuda', 'mps').")
    tokenizer: Optional[str] = Field(default=None, description="HuggingFace tokenizer id used by token-aware chunkers (e.g. hybrid); loaded once and shared across actions.")
    actions: List[DoclingDocumentLoaderActionConfig] = Field(default_factory=list)
