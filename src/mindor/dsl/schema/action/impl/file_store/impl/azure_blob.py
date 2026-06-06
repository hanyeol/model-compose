from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from .common import (
    CommonFilePutActionConfig,
    CommonFileGetActionConfig,
    CommonFileDeleteActionConfig,
    CommonFileExistsActionConfig,
    CommonFileListActionConfig,
)

class AzureBlobFilePutActionConfig(CommonFilePutActionConfig):
    pass

class AzureBlobFileGetActionConfig(CommonFileGetActionConfig):
    pass

class AzureBlobFileDeleteActionConfig(CommonFileDeleteActionConfig):
    pass

class AzureBlobFileExistsActionConfig(CommonFileExistsActionConfig):
    pass

class AzureBlobFileListActionConfig(CommonFileListActionConfig):
    pass

AzureBlobFileStoreActionConfig = Annotated[
    Union[
        AzureBlobFilePutActionConfig,
        AzureBlobFileGetActionConfig,
        AzureBlobFileDeleteActionConfig,
        AzureBlobFileExistsActionConfig,
        AzureBlobFileListActionConfig,
    ],
    Field(discriminator="method")
]
