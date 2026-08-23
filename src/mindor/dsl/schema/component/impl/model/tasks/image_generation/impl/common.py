from typing import Literal, Union, Optional, Dict, Any
from pydantic import BaseModel, Field, model_validator
from mindor.dsl.utils.path import is_local_path
from mindor.dsl.schema.action import ImageGenerationActionMethod
from ...common import CommonModelComponentConfig, ModelConfig, ModelProvider, ModelPrecision, ModelQuantizationConfig, ModelTaskType

class VaeConfig(BaseModel):
    model: ModelConfig = Field(..., description="VAE model identifier — a HuggingFace repo ID or a local path.")
    precision: Optional[ModelPrecision] = Field(default=None, description="Numeric precision used for VAE weights and computation.")
    quantization: Optional[Union[str, ModelQuantizationConfig]] = Field(default=None, description="Quantization applied to the VAE weights.")
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

    @model_validator(mode="before")
    def inflate_quantization(cls, values: Dict[str, Any]):
        quantization = values.get("quantization")
        if isinstance(quantization, str):
            values["quantization"] = { "type": quantization }
        return values

class CommonImageGenerationModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.IMAGE_GENERATION]
    version: Optional[str] = Field(default=None, description="Model version or variant identifier within the family.")
    vae: Optional[VaeConfig] = Field(default=None, description="Overrides for the VAE component of the diffusion pipeline.")

    @model_validator(mode="before")
    def inject_default_action_method(cls, values: Dict[str, Any]):
        actions = values.get("actions")
        if actions is None:
            action = values.get("action")
            actions = [ action ] if action else []
        for action in actions:
            if isinstance(action, dict) and "method" not in action:
                action["method"] = ImageGenerationActionMethod.GENERATE
        return values

    @model_validator(mode="before")
    def inflate_vae(cls, values: Dict[str, Any]):
        vae = values.get("vae")
        if isinstance(vae, str):
            values["vae"] = { "model": vae }
        return values
