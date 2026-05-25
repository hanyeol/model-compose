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
    name: str = Field(..., description="Field name.")
    type: SearchEngineFieldType = Field(default=SearchEngineFieldType.TEXT, description="Field type: 'text' for full-text search, 'id' for exact-match identifier, 'keyword' for tag-like values.")

class CommonSearchEngineActionConfig(CommonActionConfig):
    method: SearchEngineActionMethod = Field(..., description="Search engine operation method.")

class CommonSearchIndexActionConfig(CommonSearchEngineActionConfig):
    method: Literal[SearchEngineActionMethod.INDEX]
    index: str = Field(..., description="Target index name to insert documents into.")
    fields: Optional[List[SearchEngineFieldConfig]] = Field(default=None, description="Index schema field definitions. Optional when appending to an existing index.")
    documents: Union[List[Dict[str, Any]], str] = Field(..., description="List of documents to index.")

class CommonSearchSearchActionConfig(CommonSearchEngineActionConfig):
    method: Literal[SearchEngineActionMethod.SEARCH]
    index: str = Field(..., description="Target index name to search.")
    query: Union[str, str] = Field(..., description="Search query string.")
    search_fields: Optional[Union[List[str], str]] = Field(default=None, description="Fields to search in. When omitted, all text fields are searched.")
    limit: Union[int, str] = Field(default=10, description="Maximum number of search results to return.")

class CommonSearchDeleteActionConfig(CommonSearchEngineActionConfig):
    method: Literal[SearchEngineActionMethod.DELETE]
    index: str = Field(..., description="Target index name to delete documents from.")
    document_ids: Union[List[str], str] = Field(..., description="List of document ID values to delete.")
