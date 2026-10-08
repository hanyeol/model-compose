from typing import Optional, Literal
from pydantic import Field
from .common import CommonDocumentLoaderActionConfig

class PymupdfDocumentLoaderActionConfig(CommonDocumentLoaderActionConfig):
    password: Optional[str] = Field(default=None, description="Password used to decrypt the PDF when it is encrypted.")
    extraction_mode: Literal["text", "blocks", "html", "json"] = Field(default="text", description="Text extraction mode: 'text', 'blocks', 'html', or 'json'.")
    page_range: Optional[str] = Field(default=None, description="Page range to extract (e.g. '1-5,7'); all pages when omitted.")
