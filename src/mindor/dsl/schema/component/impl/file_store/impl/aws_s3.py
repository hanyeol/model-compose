from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import AwsS3FileStoreActionConfig
from .common import CommonFileStoreComponentConfig, FileStoreDriver

class AwsS3FileStoreComponentConfig(CommonFileStoreComponentConfig):
    driver: Literal[FileStoreDriver.AWS_S3]
    bucket: str = Field(..., description="Name of the S3 bucket that backs this store.")
    region: Optional[str] = Field(default=None, description="AWS region hosting the bucket; falls back to the SDK default when unset.")
    endpoint: Optional[str] = Field(default=None, description="Custom endpoint URL for S3-compatible storage (e.g., MinIO, R2).")
    access_key_id: Optional[str] = Field(default=None, description="AWS access key ID; resolved from the environment or IAM role when unset.")
    secret_access_key: Optional[str] = Field(default=None, description="AWS secret access key; resolved from the environment or IAM role when unset.")
    session_token: Optional[str] = Field(default=None, description="AWS session token for temporary STS credentials.")
    actions: List[AwsS3FileStoreActionConfig] = Field(default_factory=list)
