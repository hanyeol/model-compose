from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from .common import CommonActionConfig

class TextRendererActionConfig(CommonActionConfig):
    template: Union[str, List[str]] = Field(..., description="Template text to render into the action output.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input templates processed per batch.")
