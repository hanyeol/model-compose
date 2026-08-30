from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from ..common import ComponentType, component_validator
from .impl import *

FileStoreComponentConfig = Annotated[
    Union[
        LocalFileStoreComponentConfig,
        AwsS3FileStoreComponentConfig,
        GcpStorageFileStoreComponentConfig,
        AzureBlobFileStoreComponentConfig,
        SftpFileStoreComponentConfig,
    ],
    Field(discriminator="driver")
]

@component_validator(ComponentType.FILE_STORE, mode="before")
def inflate_default_driver(values: Dict[str, Any]) -> None:
    if "driver" not in values:
        values["driver"] = FileStoreDriver.LOCAL
