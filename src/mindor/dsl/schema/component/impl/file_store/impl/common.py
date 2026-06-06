from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from ...common import CommonComponentConfig, ComponentType

class FileStoreDriver(str, Enum):
    LOCAL       = "local"
    AWS_S3      = "aws-s3"
    GCP_STORAGE = "gcp-storage"
    AZURE_BLOB  = "azure-blob"

class CommonFileStoreComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.FILE_STORE]
    driver: FileStoreDriver = Field(..., description="File store backend driver.")
    base_path: Optional[str] = Field(default=None, description="Base path or key prefix prepended to all action paths. Not included in logical paths exposed to users.")
