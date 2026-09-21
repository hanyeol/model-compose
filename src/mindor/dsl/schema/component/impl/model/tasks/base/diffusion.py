from typing import Literal, Union, Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, model_validator
from mindor.dsl.utils.path import is_local_path
from ..common import ModelConfig, ModelProvider, ModelPrecision

class DiffusionSubmodule(str, Enum):
    TEXT_ENCODER   = "text_encoder"
    TEXT_ENCODER_2 = "text_encoder_2"
    TEXT_ENCODER_3 = "text_encoder_3"
    TRANSFORMER    = "transformer"
    UNET           = "unet"
    VAE            = "vae"
    IMAGE_ENCODER  = "image_encoder"

DiffusionCpuOffload = Union[Literal["model", "sequential"], List[DiffusionSubmodule]]

class DiffusionVaeConfig(BaseModel):
    model: ModelConfig = Field(..., description="VAE model identifier — a HuggingFace repo ID or a local path.")
    precision: Optional[ModelPrecision] = Field(default=None, description="Numeric precision used for VAE weights and computation.")
    low_cpu_mem_usage: Union[bool, str] = Field(default=False, description="Whether to load the VAE with reduced CPU RAM usage.")

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
