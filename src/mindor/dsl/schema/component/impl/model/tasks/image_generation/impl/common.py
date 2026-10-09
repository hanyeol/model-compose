from typing import Literal, List, Optional, Dict, Any
from pydantic import Field, model_validator
from mindor.dsl.schema.action import ImageGenerationActionMethod
from ...common import CommonModelComponentConfig, ModelTaskType
from ...base.diffusion import DiffusionVaeConfig, DiffusionControlNetConfig

class CommonImageGenerationModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.IMAGE_GENERATION]
    version: Optional[str] = Field(default=None, description="Model version or variant identifier within the family.")
    vae: Optional[DiffusionVaeConfig] = Field(default=None, description="Overrides for the VAE component of the diffusion pipeline.")
    controlnet: Optional[List[DiffusionControlNetConfig]] = Field(default=None, description="ControlNet models conditioning the diffusion pipeline; accepts a single entry or a list for stacking multiple ControlNets.")

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

    @model_validator(mode="before")
    def normalize_controlnet(cls, values: Dict[str, Any]):
        controlnet = values.get("controlnet", None)
        if controlnet is not None:
            controlnets = []
            if not isinstance(controlnet, list):
                controlnet = [ controlnet ]
            for value in controlnet:
                if isinstance(value, str):
                    controlnets.append({ "model": value })
                else:
                    controlnets.append(value)
            values["controlnet"] = controlnets
        return values
