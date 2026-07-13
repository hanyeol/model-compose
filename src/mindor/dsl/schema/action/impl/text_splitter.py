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
    text: Union[str, List[str]] = Field(..., description="Input text(s) to split.")
    language: Optional[TextSplitterLanguage] = Field(default=None, description="Language preset for separators. Mutually exclusive with 'separators'.")
    separators: Optional[List[str]] = Field(default=None, description="Separators for splitting. Mutually exclusive with 'language'.")
    chunk_size: Union[int, str] = Field(default=1000, description="Maximum characters per chunk.")
    chunk_overlap: Union[int, str] = Field(default=200, description="Overlapping characters between chunks.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input texts per batch.")
    streaming: Union[bool, str] = Field(default=False, description="Whether to stream chunks one by one instead of returning a full list.")

    @model_validator(mode="after")
    def validate_language_or_separators(self):
        if self.language is not None and self.separators:
            raise ValueError("Cannot specify both 'language' and 'separators' on text-splitter action; choose one.")
        return self
