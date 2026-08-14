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
    driver: FileStoreDriver = Field(..., description="Backend implementation used for the file store.")
    base_path: Optional[str] = Field(default=None, description="Path or key prefix prepended to every action's target path.")
