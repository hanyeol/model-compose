from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from .common import CommonDatasetsLoadActionConfig, DatasetsProvider

class HuggingfaceDatasetsLoadActionConfig(CommonDatasetsLoadActionConfig):
    provider: Literal[DatasetsProvider.HUGGINGFACE]
    path: str = Field(..., description="HuggingFace dataset name or path.")
    name: Optional[str] = Field(default=None, description="Dataset configuration name.")
    revision: Optional[str] = Field(default=None, description="Dataset revision/version to load.")
    token: Optional[str] = Field(default=None, description="Authentication token for private datasets.")
    trust_remote_code: Union[bool, str] = Field(default=False, description="Allow executing remote code for dataset loading.")
