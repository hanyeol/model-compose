from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from .impl import *

FileStoreComponentConfig = Annotated[
    Union[
        LocalFileStoreComponentConfig,
        AwsS3FileStoreComponentConfig,
        GcpStorageFileStoreComponentConfig,
        AzureBlobFileStoreComponentConfig,
    ],
    Field(discriminator="driver")
]
