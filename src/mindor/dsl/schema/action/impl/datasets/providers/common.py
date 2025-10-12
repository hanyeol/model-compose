from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from ..common import CommonDatasetsActionConfig, DatasetsActionMethod

class DatasetsProvider(str, Enum):
    HUGGINGFACE = "huggingface"
    LOCAL       = "local"

class CommonDatasetsLoadActionConfig(CommonDatasetsActionConfig):
    method: Literal[DatasetsActionMethod.LOAD]
    provider: DatasetsProvider = Field(..., description="Datasets provider configuration.")
    split: Optional[str] = Field(default=None, description="Dataset split to load (e.g., 'train', 'test', 'validation').")
    streaming: Union[bool, str] = Field(default=False, description="Enable streaming mode for large datasets.")
    keep_in_memory: Union[bool, str] = Field(default=False, description="Keep dataset in memory.")
    cache_dir: Optional[str] = Field(default=None, description="Directory to cache downloaded files.")
    save_infos: Union[bool, str] = Field(default=False, description="Save dataset info to cache.")
    fraction: Optional[Union[float, str]] = Field(default=None, description="Fraction of dataset to load.")
    shuffle: bool = Field(default=False, description="Shuffle dataset before applying fraction selection.")
