from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import GcpStorageFileStoreActionConfig
from .common import CommonFileStoreComponentConfig, FileStoreDriver

class GcpStorageFileStoreComponentConfig(CommonFileStoreComponentConfig):
    driver: Literal[FileStoreDriver.GCP_STORAGE]
    bucket: str = Field(..., description="GCS bucket name.")
    project: Optional[str] = Field(default=None, description="GCP project ID. If not set, SDK default is used.")
    endpoint: Optional[str] = Field(default=None, description="Custom endpoint URL for GCS-compatible storage.")
    credentials_path: Optional[str] = Field(default=None, description="Path to service account JSON key file.")
    actions: List[GcpStorageFileStoreActionConfig] = Field(default_factory=list)
