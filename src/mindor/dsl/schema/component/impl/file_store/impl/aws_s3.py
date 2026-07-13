from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import AwsS3FileStoreActionConfig
from .common import CommonFileStoreComponentConfig, FileStoreDriver

class AwsS3FileStoreComponentConfig(CommonFileStoreComponentConfig):
    driver: Literal[FileStoreDriver.AWS_S3]
    bucket: str = Field(..., description="S3 bucket name.")
    region: Optional[str] = Field(default=None, description="AWS region. If not set, SDK default is used.")
    endpoint: Optional[str] = Field(default=None, description="Custom endpoint URL for S3-compatible storage (MinIO, R2, etc).")
    access_key_id: Optional[str] = Field(default=None, description="AWS access key ID. Loaded from environment or IAM role if unset.")
    secret_access_key: Optional[str] = Field(default=None, description="AWS secret access key. Loaded from environment or IAM role if unset.")
    session_token: Optional[str] = Field(default=None, description="AWS session token for temporary STS credentials.")
    actions: List[AwsS3FileStoreActionConfig] = Field(default_factory=list)
