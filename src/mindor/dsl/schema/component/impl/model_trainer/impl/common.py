from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator
from ...common import CommonComponentConfig, ComponentType
from ...model import PeftAdapterType, ModelQuantization

class TrainingTaskType(str, Enum):
    SFT            = "sft"
    CLASSIFICATION = "classification"

class CommonModelTrainerComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.MODEL_TRAINER]
    task: TrainingTaskType = Field(..., description="Type of training task to perform.")
    peft_adapter: Optional[PeftAdapterType] = Field(default=None, description="PEFT adapter type to use.")

    # LoRA configuration
    lora_r: int = Field(default=8, description="LoRA rank.")
    lora_alpha: int = Field(default=16, description="LoRA alpha for scaling.")
    lora_dropout: float = Field(default=0.05, description="LoRA dropout rate.")
    lora_target_modules: Optional[List[str]] = Field(default=None, description="Target modules for LoRA. If not specified, auto-detects.")
    lora_bias: Literal["none", "all", "lora_only"] = Field(default="none", description="Bias training strategy for LoRA.")

    # Quantization
    quantization: ModelQuantization = Field(default=ModelQuantization.NONE, description="Model quantization method (int4/nf4 for QLoRA, int8 for 8-bit).")
    bnb_4bit_compute_dtype: Optional[str] = Field(default=None, description="Compute dtype for 4-bit base models (e.g., 'float16', 'bfloat16').")
    bnb_4bit_use_double_quant: bool = Field(default=True, description="Use nested quantization for 4-bit.")
