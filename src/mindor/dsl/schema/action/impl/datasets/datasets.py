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
    datasets: Union[List[str], str] = Field(..., description="List of datasets to concatenate.")
    direction: Literal[ "vertical", "horizontal" ] = Field(default="vertical", description="Direction to concatenate. 'vertical' for rows (default), 'horizontal' for columns.")
    info: Optional[Any] = Field(default=None, description="Dataset info to use for the concatenated dataset.")
    split: Optional[str] = Field(default=None, description="Name of the split for the concatenated dataset.")

class DatasetsFilterActionConfig(CommonDatasetsActionConfig):
    method: Literal[DatasetsActionMethod.FILTER]

DatasetsActionConfig = Annotated[
    Union[
        DatasetsLoadActionConfig,
        DatasetsConcatActionConfig,
        DatasetsFilterActionConfig
    ],
    Field(discriminator="method")
]
