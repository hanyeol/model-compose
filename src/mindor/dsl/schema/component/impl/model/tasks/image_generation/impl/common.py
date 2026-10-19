from typing import Literal, List, Optional, Dict, Any
from pydantic import Field, model_validator
from mindor.dsl.schema.action import ImageGenerationActionMethod
from ...common import CommonModelComponentConfig, ModelSubmoduleConfig, ModelTaskType

class CommonImageGenerationModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.IMAGE_GENERATION]
    version: Optional[str] = Field(default=None, description="Model version or variant identifier within the family.")
    vae: Optional[ModelSubmoduleConfig] = Field(default=None, description="Overrides for the VAE component of the diffusion pipeline.")
    controlnet: Optional[List[ModelSubmoduleConfig]] = Field(default=None, description="ControlNet models conditioning the diffusion pipeline; accepts a single entry or a list for stacking multiple ControlNets.")

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
    def normalize_controlnet(cls, values: Dict[str, Any]):
        controlnet = values.get("controlnet", None)
        if controlnet is not None and not isinstance(controlnet, list):
            values["controlnet"] = [ controlnet ]
        return values
