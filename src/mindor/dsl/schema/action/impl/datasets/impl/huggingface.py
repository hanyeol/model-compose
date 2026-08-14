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
    path: str = Field(..., description="HuggingFace Hub repo id (e.g., squad) or a built-in builder name for local files (e.g., json, csv, parquet, text).")
    name: Optional[str] = Field(default=None, description="Dataset configuration name (e.g., GLUE's mrpc). Hub datasets only.")
    revision: Optional[str] = Field(default=None, description="Dataset revision or version. Hub datasets only.")
    token: Optional[str] = Field(default=None, description="Authentication token used for private Hub datasets.")
    trust_remote_code: Union[bool, str] = Field(default=False, description="Whether remote loader code is allowed to execute during loading.")
    data_files: Optional[Union[str, List[str], Dict[str, str]]] = Field(default=None, description="Data files consumed when `path` is a built-in builder name.")
    data_dir: Optional[str] = Field(default=None, description="Directory of data files consumed when `path` is a built-in builder name.")

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
