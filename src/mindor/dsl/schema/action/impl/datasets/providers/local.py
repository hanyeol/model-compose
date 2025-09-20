from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from .common import CommonDatasetsLoadActionConfig, DatasetsProvider

class LocalDatasetsLoadActionConfig(CommonDatasetsLoadActionConfig):
    provider: Literal[DatasetsProvider.LOCAL]
    loader: str = Field(..., description="Dataset loader type (e.g., 'json', 'csv', 'parquet', 'text')")
    data_files: Optional[Union[str, List[str], Dict[str, str]]] = Field(default=None, description="Path to data files.")
    data_dir: Optional[str] = Field(default=None, description="Directory containing data files.")
