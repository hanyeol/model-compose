from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator
from mindor.dsl.utils.path import is_local_path
from ...common import CommonComponentConfig, ComponentType
from ...model import ModelConfig, ModelProvider, ModelPrecision, ModelQuantizationConfig

class ModelTrainerTaskType(str, Enum):
    SFT                 = "sft"
    TEXT_CLASSIFICATION = "text-classification"

class ModelTrainerDriverType(str, Enum):
    HUGGINGFACE = "huggingface"

class ModelTrainerLoraConfig(BaseModel):
    rank: int = Field(default=8, description="Rank of the LoRA decomposition.")
    alpha: int = Field(default=16, description="Scaling factor applied to LoRA updates.")
    dropout: float = Field(default=0.05, description="Dropout probability applied within LoRA layers.")
    target_modules: Optional[List[str]] = Field(default=None, description="Module names to attach LoRA adapters to; auto-detected when unset.")
    bias: Literal[ "none", "all", "lora_only" ] = Field(default="none", description="Which bias parameters are trained alongside LoRA weights.")

class CommonModelTrainerComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.MODEL_TRAINER]
    task: ModelTrainerTaskType = Field(..., description="Training task the trainer performs.")
    driver: ModelTrainerDriverType = Field(..., description="Backend used to run training.")
    model: ModelConfig = Field(..., description="Base model to fine-tune — a HuggingFace repo ID or a local path.")
    device: str = Field(default="auto", description="Compute device (cpu, cuda, cuda:0, mps, auto).")
    precision: Optional[ModelPrecision] = Field(default=None, description="Model load precision (float32, float16, bfloat16, auto).")
    lora: Optional[ModelTrainerLoraConfig] = Field(default=None, description="LoRA adapter settings used during training.")
    quantization: Optional[ModelQuantizationConfig] = Field(default=None, description="Quantization applied to the base model during training.")

    @model_validator(mode="before")
    def inflate_model(cls, values: Dict[str, Any]):
        model = values.get("model")
        if isinstance(model, str):
            if is_local_path(model):
                values["model"] = { "provider": ModelProvider.LOCAL, "path": model }
            else:
                values["model"] = { "provider": ModelProvider.HUGGINGFACE, "repository": model }
        return values

    @model_validator(mode="before")
    def fill_missing_model_provider(cls, values: Dict[str, Any]):
        model = values.get("model")
        if isinstance(model, dict) and "provider" not in model:
            if "repository" in model:
                model["provider"] = ModelProvider.HUGGINGFACE
            elif "name" in model:
                model["provider"] = ModelProvider.NAMED
            else:
                model["provider"] = ModelProvider.LOCAL
        return values

    @model_validator(mode="before")
    def inflate_quantization(cls, values: Dict[str, Any]):
        quantization = values.get("quantization")
        if isinstance(quantization, str):
            values["quantization"] = { "type": quantization }
        return values

    @model_validator(mode="after")
    def validate_quantization_requires_lora(self):
        # bitsandbytes quantization + prepare_model_for_kbit_training() freezes every
        # base parameter. Without a LoRA adapter (or another trainable-parameter path,
        # which this scope does not support) there is nothing left to update, and
        # training silently loses all gradients. Reject the combination explicitly.
        if self.quantization is not None and self.lora is None:
            raise ValueError(
                "quantization requires 'lora' to be set — training a fully-quantized "
                "base model with no trainable adapter is not supported."
            )
        return self
