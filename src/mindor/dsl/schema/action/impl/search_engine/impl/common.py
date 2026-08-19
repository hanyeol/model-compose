from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from ...common import CommonActionConfig

class SearchEngineActionMethod(str, Enum):
    INDEX  = "index"
    SEARCH = "search"
    DELETE = "delete"

class SearchEngineFieldType(str, Enum):
    TEXT    = "text"
    ID      = "id"
    KEYWORD = "keyword"

class SearchEngineFieldConfig(BaseModel):
    name: str = Field(..., description="Name of the indexed field.")
    type: SearchEngineFieldType = Field(default=SearchEngineFieldType.TEXT, description="How the field's values are analyzed and stored.")

class CommonSearchEngineActionConfig(CommonActionConfig):
    method: SearchEngineActionMethod = Field(..., description="Search engine operation this action performs.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of items processed per batch.")

class CommonSearchIndexActionConfig(CommonSearchEngineActionConfig):
    method: Literal[SearchEngineActionMethod.INDEX]
    index: str = Field(..., description="Name of the index that receives the documents.")
    fields: Optional[List[SearchEngineFieldConfig]] = Field(default=None, description="Index schema field definitions; optional when appending to an existing index.")
    document: Union[Dict[str, Any], List[Dict[str, Any]], str] = Field(..., description="Document or documents inserted into the index.")

class CommonSearchSearchActionConfig(CommonSearchEngineActionConfig):
    method: Literal[SearchEngineActionMethod.SEARCH]
    index: str = Field(..., description="Name of the index searched by this action.")
    query: Union[str, List[str]] = Field(..., description="Search query or list of queries.")
    search_fields: Optional[Union[List[str], str]] = Field(default=None, description="Fields the query runs against; when omitted, all text fields are searched.")
    limit: Union[int, str] = Field(default=10, description="Maximum number of search results returned.")

class CommonSearchDeleteActionConfig(CommonSearchEngineActionConfig):
    method: Literal[SearchEngineActionMethod.DELETE]
    index: str = Field(..., description="Name of the index that documents are deleted from.")
    document_id: Union[str, List[str]] = Field(..., description="ID or IDs of the documents to delete.")
