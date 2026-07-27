from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from .common import (
    DatasetsDriver,
    CommonDatasetsLoadActionConfig,
    CommonDatasetsConcatActionConfig,
    CommonDatasetsSelectActionConfig,
    CommonDatasetsFilterActionConfig,
    CommonDatasetsMapActionConfig,
)

class HuggingfaceDatasetsLoadActionConfig(CommonDatasetsLoadActionConfig):
    path: str = Field(..., description="HuggingFace Hub repo id (e.g., 'squad') or a built-in builder name for local files ('json', 'csv', 'parquet', 'text', ...).")
    name: Optional[str] = Field(default=None, description="Dataset configuration name (e.g., GLUE's 'mrpc'). Hub datasets only.")
    revision: Optional[str] = Field(default=None, description="Dataset revision/version. Hub datasets only.")
    token: Optional[str] = Field(default=None, description="Authentication token for private Hub datasets.")
    trust_remote_code: Union[bool, str] = Field(default=False, description="Allow executing remote loader code when loading.")
    data_files: Optional[Union[str, List[str], Dict[str, str]]] = Field(default=None, description="Path to data files. Used when `path` is a built-in builder name.")
    data_dir: Optional[str] = Field(default=None, description="Directory containing data files. Used when `path` is a built-in builder name.")

class HuggingfaceDatasetsConcatActionConfig(CommonDatasetsConcatActionConfig):
    pass

class HuggingfaceDatasetsSelectActionConfig(CommonDatasetsSelectActionConfig):
    pass

class HuggingfaceDatasetsFilterActionConfig(CommonDatasetsFilterActionConfig):
    pass

class HuggingfaceDatasetsMapActionConfig(CommonDatasetsMapActionConfig):
    pass

HuggingfaceDatasetsActionConfig = Annotated[
    Union[
        HuggingfaceDatasetsLoadActionConfig,
        HuggingfaceDatasetsConcatActionConfig,
        HuggingfaceDatasetsSelectActionConfig,
        HuggingfaceDatasetsFilterActionConfig,
        HuggingfaceDatasetsMapActionConfig,
    ],
    Field(discriminator="method")
]
