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
    metadata: Optional[Dict[str, str]] = Field(default=None, description="Object metadata (cloud drivers only; ignored by the local driver).")
    multipart_threshold: Optional[Union[int, str]] = Field(default=None, description="Files larger than this are uploaded in multiple parts. Cloud drivers only. Default 8MB.")
    chunk_size: Optional[Union[int, str]] = Field(default=None, description="Size of each data chunk read/written during upload. Default is driver-specific (typically 8MB).")

class CommonFileGetActionConfig(CommonFileStoreActionConfig):
    method: Literal[FileStoreActionMethod.GET]
    path: str = Field(..., description="Path within the store, relative to the component's base_path.")
    save_to: Optional[str] = Field(default=None, description="Local filesystem path to save the data. When set, data is streamed directly to the file instead of loaded into memory. If an existing directory is given, the file is saved inside it using the basename of `path`.")
    streaming: Union[bool, str] = Field(default=False, description="If true, hand the data to subsequent jobs as a chunked stream instead of buffering it in memory. Supports ${...} variable references.")
    chunk_size: Optional[Union[int, str]] = Field(default=None, description="Size of each data chunk read during download. Default depends on usage: 8MB when downloading to `save_to`, 8KB when handing off as a stream. Ignored when neither is set.")

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
    path: Optional[str] = Field(default=None, description="Path prefix to filter by, relative to the component's base_path. Local lists directory contents; cloud drivers match key prefixes.")
    recursive: Union[bool, str] = Field(default=False, description="If true, descend into subdirectories. Local driver only; cloud drivers always list by prefix. Supports ${...} variable references.")
    pattern: Optional[str] = Field(default=None, description="Glob pattern to filter results by relative path (e.g. `*.jpg`, `**/*.png`). Matched against each file's path relative to the component's base_path.")
    max_result_count: Optional[int] = Field(default=None, ge=1, description="Maximum number of items to return per response. Use next_token for pagination.")
    next_token: Optional[str] = Field(default=None, description="Pagination token from the previous response's `next_token` result. Omit on the first call.")
