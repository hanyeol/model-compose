from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from .common import (
    CommonFilePutActionConfig,
    CommonFileGetActionConfig,
    CommonFileDeleteActionConfig,
    CommonFileExistsActionConfig,
    CommonFileListActionConfig,
)

class LocalFilePutActionConfig(CommonFilePutActionConfig):
    pass

class LocalFileGetActionConfig(CommonFileGetActionConfig):
    pass

class LocalFileDeleteActionConfig(CommonFileDeleteActionConfig):
    pass

class LocalFileExistsActionConfig(CommonFileExistsActionConfig):
    pass

class LocalFileListActionConfig(CommonFileListActionConfig):
    pass

LocalFileStoreActionConfig = Annotated[
    Union[
        LocalFilePutActionConfig,
        LocalFileGetActionConfig,
        LocalFileDeleteActionConfig,
        LocalFileExistsActionConfig,
        LocalFileListActionConfig,
    ],
    Field(discriminator="method")
]
