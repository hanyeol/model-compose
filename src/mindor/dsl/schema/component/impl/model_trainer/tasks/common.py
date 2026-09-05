from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator
from ...common import CommonComponentConfig, ComponentType
from ...model import ModelQuantizationConfig

class ModelTrainerTaskType(str, Enum):
    SFT            = "sft"
    CLASSIFICATION = "classification"

class ModelTrainerLoraConfig(BaseModel):
    rank: int = Field(default=8, description="Rank of the LoRA decomposition.")
    alpha: int = Field(default=16, description="Scaling factor applied to LoRA updates.")
    dropout: float = Field(default=0.05, description="Dropout probability applied within LoRA layers.")
    target_modules: Optional[List[str]] = Field(default=None, description="Module names to attach LoRA adapters to; auto-detected when unset.")
    bias: Literal[ "none", "all", "lora_only" ] = Field(default="none", description="Which bias parameters are trained alongside LoRA weights.")

class CommonModelTrainerComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.MODEL_TRAINER]
    task: ModelTrainerTaskType = Field(..., description="Training task the trainer performs.")
    lora: Optional[ModelTrainerLoraConfig] = Field(default=None, description="LoRA adapter settings used during training.")
    quantization: Optional[Union[str, ModelQuantizationConfig]] = Field(default=None, description="Quantization applied to the base model during training.")

    @model_validator(mode="before")
    def inflate_quantization(cls, values: Dict[str, Any]):
        quantization = values.get("quantization")
        if isinstance(quantization, str):
            values["quantization"] = { "type": quantization }
        return values
