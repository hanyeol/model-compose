from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field, model_validator
from ...common import CommonActionConfig

class FileStoreActionMethod(str, Enum):
    PUT    = "put"
    GET    = "get"
    DELETE = "delete"
    EXISTS = "exists"
    LIST   = "list"

class CommonFileStoreActionConfig(CommonActionConfig):
    method: FileStoreActionMethod = Field(..., description="File store operation method.")

class CommonFilePutActionConfig(CommonFileStoreActionConfig):
    method: Literal[FileStoreActionMethod.PUT]
    path: str = Field(..., description="Path within the store, relative to the component's base_path.")
    source: Any = Field(..., description="Data to store.")
    content_type: Optional[str] = Field(default=None, description="MIME type. Inferred from the path extension if not specified.")
    metadata: Optional[Dict[str, str]] = Field(default=None, description="Object metadata (cloud drivers only; ignored by local driver).")
    multipart_threshold: Optional[Union[int, str]] = Field(default=None, description="Files above this size are uploaded in multiple parts.")
    chunk_size: Optional[Union[int, str]] = Field(default=None, description="Size of each chunk read/written during upload.")

class CommonFileGetActionConfig(CommonFileStoreActionConfig):
    method: Literal[FileStoreActionMethod.GET]
    path: str = Field(..., description="Path within the store, relative to the component's base_path.")
    save_to: Optional[str] = Field(default=None, description="Local filesystem path to save the data to.")
    streaming: Union[bool, str] = Field(default=False, description="Hand data to subsequent jobs as a chunked stream.")
    chunk_size: Optional[Union[int, str]] = Field(default=None, description="Size of each chunk read during download.")

    @model_validator(mode="after")
    def validate_save_to_and_streaming(self):
        if self.save_to is not None and self.streaming is True:
            raise ValueError("'save_to' and 'streaming: true' cannot both be set.")
        return self

class CommonFileDeleteActionConfig(CommonFileStoreActionConfig):
    method: Literal[FileStoreActionMethod.DELETE]
    path: str = Field(..., description="Path within the store to delete, relative to the component's base_path.")

class CommonFileExistsActionConfig(CommonFileStoreActionConfig):
    method: Literal[FileStoreActionMethod.EXISTS]
    path: str = Field(..., description="Path within the store to check, relative to the component's base_path.")

class CommonFileListActionConfig(CommonFileStoreActionConfig):
    method: Literal[FileStoreActionMethod.LIST]
    path: Optional[str] = Field(default=None, description="Path prefix to filter by.")
    recursive: Union[bool, str] = Field(default=False, description="Descend into subdirectories.")
    pattern: Optional[str] = Field(default=None, description="Glob pattern to filter results by relative path.")
    max_result_count: Optional[int] = Field(default=None, ge=1, description="Maximum items per response. Use next_token for pagination.")
    next_token: Optional[str] = Field(default=None, description="Pagination token from the previous response.")
