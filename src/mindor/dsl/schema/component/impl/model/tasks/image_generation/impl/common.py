from typing import Literal, Optional, Dict, Any
from pydantic import Field, model_validator
from mindor.dsl.schema.action import ImageGenerationActionMethod
from ...common import CommonModelComponentConfig, ModelTaskType
from ...base.diffusion import DiffusionVaeConfig

class CommonImageGenerationModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.IMAGE_GENERATION]
    version: Optional[str] = Field(default=None, description="Model version or variant identifier within the family.")
    vae: Optional[DiffusionVaeConfig] = Field(default=None, description="Overrides for the VAE component of the diffusion pipeline.")

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
