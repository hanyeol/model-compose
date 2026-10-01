from typing import Literal, Union, List, Annotated, Optional, Dict, Any
from enum import Enum
from pydantic import Field, model_validator
from mindor.dsl.schema.action import KimodoMotionGenerationModelActionConfig
from ..common import CommonMotionGenerationModelComponentConfig
from .common import MotionGenerationModelFamily
from ....common import ModelDriverType, ModelProvider, HuggingfaceModelConfig, LocalModelConfig

class KimodoCfgType(str, Enum):
    NOCFG     = "nocfg"
    REGULAR   = "regular"
    SEPARATED = "separated"

# NVIDIA publishes each Kimodo checkpoint under nvidia/<preset>; the preset
# string is both the model short key passed to kimodo.load_model and the HF
# repo name, so default `model` can be derived from `preset`.
_DEFAULT_KIMODO_PRESET = "Kimodo-SOMA-RP-v1.1"

KimodoMotionGenerationModelConfig = Annotated[
    Union[
        HuggingfaceModelConfig,
        LocalModelConfig,
    ],
    Field(discriminator="provider")
]

class KimodoMotionGenerationModelComponentConfig(CommonMotionGenerationModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[MotionGenerationModelFamily.KIMODO]
    preset: str = Field(default=_DEFAULT_KIMODO_PRESET, description="Kimodo model short key or display name (e.g. Kimodo-SOMA-RP-v1.1, soma, g1).")
    model: KimodoMotionGenerationModelConfig = Field(..., description="Kimodo checkpoint — a HuggingFace repo ID or a local directory; derived from `preset` when omitted.")
    cfg_type: KimodoCfgType = Field(default=KimodoCfgType.SEPARATED, description="Classifier-free guidance strategy (nocfg, regular, separated).")
    text_encoder_device: Optional[str] = Field(default=None, description="Device override for the text encoder (e.g. 'cpu' to keep VRAM under 3 GiB).")
    text_encoder_fp32: bool = Field(default=False, description="Whether to run the text encoder in fp32 instead of the default bfloat16.")
    actions: List[KimodoMotionGenerationModelActionConfig] = Field(default_factory=list, description="Actions this Kimodo motion generation component exposes to workflows.")

    @model_validator(mode="before")
    def inflate_model_from_preset(cls, values: Dict[str, Any]):
        if values.get("model") is None:
            preset = values.get("preset", _DEFAULT_KIMODO_PRESET)
            values["model"] = {
                "provider": ModelProvider.HUGGINGFACE,
                "repository": f"nvidia/{preset}",
            }
        return values
