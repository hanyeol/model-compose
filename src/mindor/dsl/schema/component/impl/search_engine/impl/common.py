from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from ...common import CommonComponentConfig, ComponentType

class SearchEngineDriverType(str, Enum):
    SQLITE = "sqlite"

class CommonSearchEngineComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.SEARCH_ENGINE]
    driver: SearchEngineDriverType = Field(..., description="Backend implementation used for the search engine.")
