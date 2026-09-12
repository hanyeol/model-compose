from typing import Union, Optional, Literal
from pydantic import Field
from .common import CommonDocumentLoaderActionConfig

class DoclingDocumentLoaderActionConfig(CommonDocumentLoaderActionConfig):
    chunker: Optional[Union[Literal[ "hierarchical", "hybrid", "line", "page" ], str]] = Field(default="hybrid", description="Chunking strategy applied to the parsed document; omit to emit the whole document without chunking.")
    max_token_count: Optional[Union[int, str]] = Field(default=None, description="Maximum tokens per chunk for token-aware chunkers.")
    merge_peers: Union[bool, str] = Field(default=True, description="Whether adjacent under-sized chunks with matching headings/captions are merged (hybrid chunker).")
    repeat_table_header: Union[bool, str] = Field(default=True, description="Whether the table header row is repeated across chunks that split a table (hybrid chunker).")
    omit_header_on_overflow: Union[bool, str] = Field(default=False, description="Whether the heading prefix is dropped when a chunk overflows the token budget (hybrid chunker).")
    always_emit_headings: Union[bool, str] = Field(default=False, description="Whether headings are emitted as their own chunks in addition to being attached to following content (hierarchical chunker).")
    code_chunking_strategy: Optional[Union[Literal[ "standard" ], str]] = Field(default=None, description="Strategy for splitting fenced code blocks (hierarchical chunker).")
    max_line_count: Optional[Union[int, str]] = Field(default=None, description="Number of lines per chunk for the line chunker.")
    return_enriched_text: Union[bool, str] = Field(default=False, description="Whether each chunk includes an 'enriched_text' field with heading/caption prefixes prepended for embedding or LLM use.")
