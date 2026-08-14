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
    method: FileStoreActionMethod = Field(..., description="File store operation this action performs.")

class CommonFilePutActionConfig(CommonFileStoreActionConfig):
    method: Literal[FileStoreActionMethod.PUT]
    path: str = Field(..., description="Path within the store, relative to the component's base path.")
    source: Any = Field(..., description="Data written to the file store.")
    content_type: Optional[str] = Field(default=None, description="MIME type of the stored object; inferred from the path extension when omitted.")
    metadata: Optional[Dict[str, str]] = Field(default=None, description="Object metadata attached to the stored file (cloud drivers only; ignored by the local driver).")
    multipart_threshold: Optional[Union[int, str]] = Field(default=None, description="Size above which files are uploaded in multiple parts.")
    chunk_size: Optional[Union[int, str]] = Field(default=None, description="Chunk size used when reading and writing during upload.")

class CommonFileGetActionConfig(CommonFileStoreActionConfig):
    method: Literal[FileStoreActionMethod.GET]
    path: str = Field(..., description="Path within the store, relative to the component's base path.")
    save_to: Optional[str] = Field(default=None, description="Local filesystem path where the downloaded data is written.")
    streaming: Union[bool, str] = Field(default=False, description="Whether downloaded data is emitted incrementally as a chunked stream.")
    chunk_size: Optional[Union[int, str]] = Field(default=None, description="Chunk size used when reading during download.")

    @model_validator(mode="after")
    def validate_save_to_and_streaming(self):
        if self.save_to is not None and self.streaming is True:
            raise ValueError("'save_to' and 'streaming: true' cannot both be set.")
        return self

class CommonFileDeleteActionConfig(CommonFileStoreActionConfig):
    method: Literal[FileStoreActionMethod.DELETE]
    path: str = Field(..., description="Path within the store to delete, relative to the component's base path.")

class CommonFileExistsActionConfig(CommonFileStoreActionConfig):
    method: Literal[FileStoreActionMethod.EXISTS]
    path: str = Field(..., description="Path within the store to check, relative to the component's base path.")

class CommonFileListActionConfig(CommonFileStoreActionConfig):
    method: Literal[FileStoreActionMethod.LIST]
    path: Optional[str] = Field(default=None, description="Path prefix filtering listed entries.")
    recursive: Union[bool, str] = Field(default=False, description="Whether listing descends into subdirectories.")
    pattern: Optional[str] = Field(default=None, description="Glob pattern applied to each entry's relative path.")
    max_result_count: Optional[int] = Field(default=None, ge=1, description="Maximum number of items returned per response; use `next_token` for pagination.")
    next_token: Optional[str] = Field(default=None, description="Pagination token returned by the previous listing response.")
