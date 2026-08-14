from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonActionConfig

class TextSplitterLanguage(str, Enum):
    PYTHON     = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JAVA       = "java"
    KOTLIN     = "kotlin"
    SCALA      = "scala"
    GO         = "go"
    RUST       = "rust"
    CPP        = "cpp"
    C          = "c"
    CSHARP     = "csharp"
    RUBY       = "ruby"
    PHP        = "php"
    SWIFT      = "swift"
    HTML       = "html"
    MARKDOWN   = "markdown"
    LATEX      = "latex"
    SQL        = "sql"
    SOLIDITY   = "solidity"
    PROTO      = "proto"

class TextSplitterActionConfig(CommonActionConfig):
    text: Union[str, List[str]] = Field(..., description="Input text or list of texts to split.")
    language: Optional[TextSplitterLanguage] = Field(default=None, description="Language preset that selects idiomatic separators. Mutually exclusive with `separators`.")
    separators: Optional[List[str]] = Field(default=None, description="Custom separators tried in order when splitting. Mutually exclusive with `language`.")
    chunk_size: Union[int, str] = Field(default=1000, description="Maximum number of characters per output chunk.")
    chunk_overlap: Union[int, str] = Field(default=200, description="Number of characters that overlap between adjacent chunks.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input texts processed per batch.")
    streaming: Union[bool, str] = Field(default=False, description="Whether chunks are emitted incrementally as they are produced.")

    @model_validator(mode="after")
    def validate_language_or_separators(self):
        if self.language is not None and self.separators:
            raise ValueError("Cannot specify both 'language' and 'separators' on text-splitter action; choose one.")
        return self
