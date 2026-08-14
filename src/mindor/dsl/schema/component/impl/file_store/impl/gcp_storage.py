from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import GcpStorageFileStoreActionConfig
from .common import CommonFileStoreComponentConfig, FileStoreDriver

class GcpStorageFileStoreComponentConfig(CommonFileStoreComponentConfig):
    driver: Literal[FileStoreDriver.GCP_STORAGE]
    bucket: str = Field(..., description="Name of the GCS bucket that backs this store.")
    project: Optional[str] = Field(default=None, description="GCP project ID that owns the bucket; falls back to the SDK default when unset.")
    endpoint: Optional[str] = Field(default=None, description="Custom endpoint URL for GCS-compatible storage.")
    credentials_path: Optional[str] = Field(default=None, description="Path to the service account JSON key file used to authenticate.")
    actions: List[GcpStorageFileStoreActionConfig] = Field(default_factory=list)
