from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from .common import (
    CommonFilePutActionConfig,
    CommonFileGetActionConfig,
    CommonFileDeleteActionConfig,
    CommonFileExistsActionConfig,
    CommonFileListActionConfig,
)

class AwsS3FilePutActionConfig(CommonFilePutActionConfig):
    pass

class AwsS3FileGetActionConfig(CommonFileGetActionConfig):
    pass

class AwsS3FileDeleteActionConfig(CommonFileDeleteActionConfig):
    pass

class AwsS3FileExistsActionConfig(CommonFileExistsActionConfig):
    pass

class AwsS3FileListActionConfig(CommonFileListActionConfig):
    pass

AwsS3FileStoreActionConfig = Annotated[
    Union[
        AwsS3FilePutActionConfig,
        AwsS3FileGetActionConfig,
        AwsS3FileDeleteActionConfig,
        AwsS3FileExistsActionConfig,
        AwsS3FileListActionConfig,
    ],
    Field(discriminator="method")
]
