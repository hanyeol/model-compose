from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import LocalFileStoreActionConfig
from .common import CommonFileStoreComponentConfig, FileStoreDriver

class LocalFileStoreComponentConfig(CommonFileStoreComponentConfig):
    driver: Literal[FileStoreDriver.LOCAL]
    actions: List[LocalFileStoreActionConfig] = Field(default_factory=list)
