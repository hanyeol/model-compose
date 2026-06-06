from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from .impl import *

FileStoreActionConfig = Union[
    LocalFileStoreActionConfig,
    AwsS3FileStoreActionConfig,
    GcpStorageFileStoreActionConfig,
    AzureBlobFileStoreActionConfig,
]
