from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from .common import CommonDatasetsActionConfig, DatasetsActionMethod
from .providers import *

DatasetsLoadActionConfig = Annotated[
    Union[ 
        HuggingfaceDatasetsLoadActionConfig,
        LocalDatasetsLoadActionConfig
    ],
    Field(discriminator="provider")
]

class DatasetsConcatActionConfig(CommonDatasetsActionConfig):
    method: Literal[DatasetsActionMethod.CONCAT]

DatasetsActionConfig = Annotated[
    Union[ 
        DatasetsLoadActionConfig,
        DatasetsConcatActionConfig
    ],
    Field(discriminator="method")
]
