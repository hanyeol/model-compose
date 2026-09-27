from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from .common import CommonActionConfig

class TextParserFormat(str, Enum):
    JSON  = "json"
    YAML  = "yaml"
    CODE  = "code"
    XML   = "xml"
    LIST  = "list"
    TABLE = "table"
    REGEX = "regex"

class TextParserStrategy(str, Enum):
    FIRST   = "first"
    LAST    = "last"
    ALL     = "all"
    LARGEST = "largest"

class TextParserXmlOutput(str, Enum):
    TEXT = "text"
    DICT = "dict"

class TextParserActionConfig(CommonActionConfig):
    text: Union[str, List[str]] = Field(..., description="Input text or list of texts to parse.")
    format: Union[TextParserFormat, str] = Field(default=TextParserFormat.JSON, description="Structured format to extract from the input text.")
    strategy: Union[TextParserStrategy, str] = Field(default=TextParserStrategy.LARGEST, description="Which match to return when multiple candidates are found.")
    fallback: Optional[Any] = Field(default=None, description="Value returned when no candidate is extracted.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input texts processed per batch.")
    json_schema: Optional[Dict[str, Any]] = Field(default=None, description="JSON Schema validated against the extracted result. json format only.")
    xml_root: Optional[str] = Field(default=None, description="Extract only the block whose root tag matches. xml format only.")
    xml_output: Union[TextParserXmlOutput, str] = Field(default=TextParserXmlOutput.TEXT, description="Return the raw XML block string, or parse it into a dict. xml format only.")
    list_separator: str = Field(default=",", description="Item separator for the list format.")
    table_column_separator: str = Field(default=",", description="Column separator for the table format.")
    table_row_separator: str = Field(default="\n", description="Row separator for the table format.")
    table_header: Union[bool, str] = Field(default=True, description="If true, treat the first row as headers and return List[Dict]; else return List[List[str]].")
    table_quote: str = Field(default='"', description="Quote character for the table format.")
    regex_pattern: Optional[str] = Field(default=None, description="Regex pattern. regex format only.")
    regex_flags: str = Field(default="", description="Regex flag characters combining 'i', 's', 'm'.")
