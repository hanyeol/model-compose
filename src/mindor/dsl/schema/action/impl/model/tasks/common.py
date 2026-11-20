from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field, model_validator
from ...common import CommonActionConfig

class AppliedPeftAdapterConfig(BaseModel):
    name: str = Field(..., description="Name of a peft_adapter registered on the component.")
    weight: Union[float, str] = Field(default=1.0, description="Merge scale applied to the adapter delta.")

class CommonModelActionConfig(CommonActionConfig):
    peft_adapter: Optional[List[AppliedPeftAdapterConfig]] = Field(default=None, description="PEFT adapter(s) to activate for this action; references by name must exist on the component.")

    @model_validator(mode="before")
    def normalize_peft_adapter(cls, values: Dict[str, Any]):
        peft_adapter = values.get("peft_adapter", None)
        if peft_adapter is not None and not isinstance(peft_adapter, list):
            values["peft_adapter"] = [ peft_adapter ]
        return values
