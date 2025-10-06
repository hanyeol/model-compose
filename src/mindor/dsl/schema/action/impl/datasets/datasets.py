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

class DatasetsSelectActionConfig(CommonDatasetsActionConfig):
    method: Literal[DatasetsActionMethod.SELECT]
    dataset: str = Field(..., description="Source dataset to select from.")
    axis: Literal[ "rows", "columns" ] = Field(default="columns", description="Select rows by indices or columns by names.")
    indices: Optional[Union[List[int], str]] = Field(default=None, description="Row indices to select (for axis='rows').")
    columns: Optional[Union[List[str], str]] = Field(default=None, description="Column names to select (for axis='columns').")

class DatasetsFilterActionConfig(CommonDatasetsActionConfig):
    method: Literal[DatasetsActionMethod.FILTER]

class DatasetsMapActionConfig(CommonDatasetsActionConfig):
    method: Literal[DatasetsActionMethod.MAP]
    dataset: str = Field(..., description="Source dataset to map.")
    template: str = Field(..., description="Template string with {column_name} placeholders to be replaced with dataset column values.")
    output_column: str = Field(..., description="Name of the new column to create with the mapped values.")
    remove_columns: Optional[Union[List[str], str]] = Field(default=None, description="Columns to remove after mapping.")

DatasetsActionConfig = Annotated[
    Union[
        DatasetsLoadActionConfig,
        DatasetsConcatActionConfig,
        DatasetsSelectActionConfig,
        DatasetsFilterActionConfig,
        DatasetsMapActionConfig
    ],
    Field(discriminator="method")
]
