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
    method: DatasetsActionMethod = Field(..., description="Datasets operation this action performs.")

class CommonDatasetsLoadActionConfig(CommonDatasetsActionConfig):
    method: Literal[DatasetsActionMethod.LOAD]
    split: Optional[str] = Field(default=None, description="Dataset split to load (e.g., train, test, validation).")
    streaming: Union[bool, str] = Field(default=False, description="Whether the dataset is loaded in streaming mode for out-of-memory access.")
    keep_in_memory: Union[bool, str] = Field(default=False, description="Whether the loaded dataset is kept resident in memory.")
    cache_dir: Optional[str] = Field(default=None, description="Directory where downloaded dataset files are cached.")
    save_infos: Union[bool, str] = Field(default=False, description="Whether dataset info is written to the cache.")
    fraction: Optional[Union[float, str]] = Field(default=None, description="Fraction of the dataset to load, from 0.0 to 1.0.")
    shuffle: bool = Field(default=False, description="Whether the dataset is shuffled before `fraction` is applied.")

class CommonDatasetsConcatActionConfig(CommonDatasetsActionConfig):
    method: Literal[DatasetsActionMethod.CONCAT]
    datasets: Union[List[str], str] = Field(..., description="Datasets concatenated together.")
    direction: Literal[ "vertical", "horizontal" ] = Field(default="vertical", description="Direction along which datasets are concatenated.")
    info: Optional[Any] = Field(default=None, description="Dataset info attached to the concatenated result.")
    split: Optional[str] = Field(default=None, description="Name assigned to the split of the concatenated dataset.")

class CommonDatasetsSelectActionConfig(CommonDatasetsActionConfig):
    method: Literal[DatasetsActionMethod.SELECT]
    dataset: str = Field(..., description="Source dataset to select from.")
    axis: Literal[ "rows", "columns" ] = Field(default="columns", description="Whether to select rows by index or columns by name.")
    indices: Optional[Union[List[int], str]] = Field(default=None, description="Row indices selected when `axis` is `rows`.")
    columns: Optional[Union[List[str], str]] = Field(default=None, description="Column names selected when `axis` is `columns`.")

class CommonDatasetsFilterActionConfig(CommonDatasetsActionConfig):
    method: Literal[DatasetsActionMethod.FILTER]

class CommonDatasetsMapActionConfig(CommonDatasetsActionConfig):
    method: Literal[DatasetsActionMethod.MAP]
    dataset: str = Field(..., description="Source dataset to map over.")
    template: str = Field(..., description="String template with `{column_name}` placeholders substituted per row.")
    output_column: str = Field(..., description="Name of the new column populated by the mapped values.")
    remove_columns: Optional[Union[List[str], str]] = Field(default=None, description="Columns removed from the result after mapping.")
