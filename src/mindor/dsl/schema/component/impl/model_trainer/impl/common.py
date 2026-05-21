from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator
from ...common import CommonComponentConfig, ComponentType
from ...model import ModelQuantizationConfig

class TrainingTaskType(str, Enum):
    SFT            = "sft"
    CLASSIFICATION = "classification"

class ModelTrainerLoraConfig(BaseModel):
    rank: int = Field(default=8, description="LoRA rank.")
    alpha: int = Field(default=16, description="LoRA alpha for scaling.")
    dropout: float = Field(default=0.05, description="LoRA dropout rate.")
    target_modules: Optional[List[str]] = Field(default=None, description="Target modules for LoRA. If not specified, auto-detects.")
    bias: Literal["none", "all", "lora_only"] = Field(default="none", description="Bias training strategy for LoRA.")

class CommonModelTrainerComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.MODEL_TRAINER]
    task: TrainingTaskType = Field(..., description="Type of training task to perform.")
    lora: Optional[ModelTrainerLoraConfig] = Field(default=None, description="LoRA adapter configuration for training.")
    quantization: Optional[Union[str, ModelQuantizationConfig]] = Field(default=None, description="Quantization configuration.")

    @model_validator(mode="before")
    def inflate_quantization(cls, values: Dict[str, Any]):
        quantization = values.get("quantization")
        if isinstance(quantization, str):
            values["quantization"] = { "type": quantization }
        return values
