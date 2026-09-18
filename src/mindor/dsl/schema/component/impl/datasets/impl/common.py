from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import DatasetsDriverType
from ...common import CommonComponentConfig, ComponentType

class CommonDatasetsComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.DATASETS]
    driver: DatasetsDriverType = Field(..., description="Backend implementation used to load datasets.")
