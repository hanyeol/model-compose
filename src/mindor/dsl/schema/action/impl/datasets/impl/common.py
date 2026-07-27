from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from ...common import CommonActionConfig

class DatasetsDriver(str, Enum):
    HUGGINGFACE = "huggingface"

class DatasetsActionMethod(str, Enum):
    LOAD   = "load"
    CONCAT = "concat"
    SELECT = "select"
    FILTER = "filter"
    MAP    = "map"

class CommonDatasetsActionConfig(CommonActionConfig):
    method: DatasetsActionMethod = Field(..., description="Datasets operation method.")

class CommonDatasetsLoadActionConfig(CommonDatasetsActionConfig):
    method: Literal[DatasetsActionMethod.LOAD]
    split: Optional[str] = Field(default=None, description="Dataset split to load (e.g., 'train', 'test', 'validation').")
    streaming: Union[bool, str] = Field(default=False, description="Enable streaming mode for large datasets.")
    keep_in_memory: Union[bool, str] = Field(default=False, description="Keep dataset in memory.")
    cache_dir: Optional[str] = Field(default=None, description="Directory to cache downloaded files.")
    save_infos: Union[bool, str] = Field(default=False, description="Save dataset info to cache.")
    fraction: Optional[Union[float, str]] = Field(default=None, description="Fraction of dataset to load.")
    shuffle: bool = Field(default=False, description="Shuffle before applying fraction selection.")

class CommonDatasetsConcatActionConfig(CommonDatasetsActionConfig):
    method: Literal[DatasetsActionMethod.CONCAT]
    datasets: Union[List[str], str] = Field(..., description="List of datasets to concatenate.")
    direction: Literal[ "vertical", "horizontal" ] = Field(default="vertical", description="Direction to concatenate.")
    info: Optional[Any] = Field(default=None, description="Dataset info to use for the concatenated dataset.")
    split: Optional[str] = Field(default=None, description="Name of the split for the concatenated dataset.")

class CommonDatasetsSelectActionConfig(CommonDatasetsActionConfig):
    method: Literal[DatasetsActionMethod.SELECT]
    dataset: str = Field(..., description="Source dataset to select from.")
    axis: Literal[ "rows", "columns" ] = Field(default="columns", description="Select rows by indices or columns by names.")
    indices: Optional[Union[List[int], str]] = Field(default=None, description="Row indices to select (for axis='rows').")
    columns: Optional[Union[List[str], str]] = Field(default=None, description="Column names to select (for axis='columns').")

class CommonDatasetsFilterActionConfig(CommonDatasetsActionConfig):
    method: Literal[DatasetsActionMethod.FILTER]

class CommonDatasetsMapActionConfig(CommonDatasetsActionConfig):
    method: Literal[DatasetsActionMethod.MAP]
    dataset: str = Field(..., description="Source dataset to map.")
    template: str = Field(..., description="Template with {column_name} placeholders.")
    output_column: str = Field(..., description="Name of the new column to create with the mapped values.")
    remove_columns: Optional[Union[List[str], str]] = Field(default=None, description="Columns to remove after mapping.")
