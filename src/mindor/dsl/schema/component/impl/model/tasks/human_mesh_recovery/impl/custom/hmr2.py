from typing import Literal, Union, List, Annotated, Dict, Any
from pydantic import Field, model_validator
from mindor.dsl.schema.action import HMR2HumanMeshRecoveryModelActionConfig
from ....common import ModelDriverType, ModelProvider, HuggingfaceModelConfig, LocalModelConfig
from ..common import CommonHumanMeshRecoveryModelComponentConfig
from .common import HumanMeshRecoveryModelFamily

# 4D-Humans has no first-party HuggingFace mirror; upstream serves the bundled
# weights (ViT backbone, ViTDet detector, SMPL joint regressor, config) as a
# single tarball from the project page.
_DEFAULT_MODEL_URL = "https://www.cs.utexas.edu/~pavlakos/4dhumans/hmr2_data.tar.gz"

class HMR2LocalModelConfig(LocalModelConfig):
    def _cache_subdir(self) -> str:
        return "hmr2"

HMR2HumanMeshRecoveryModelConfig = Annotated[
    Union[
        HuggingfaceModelConfig,
        HMR2LocalModelConfig,
    ],
    Field(discriminator="provider")
]

class HMR2HumanMeshRecoveryModelComponentConfig(CommonHumanMeshRecoveryModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[HumanMeshRecoveryModelFamily.HMR2]
    model: HMR2HumanMeshRecoveryModelConfig = Field(..., description="HMR2 weights bundle — defaults to the upstream 4D-Humans tarball when omitted.")
    smpl_model: LocalModelConfig = Field(..., description="Local directory containing the gated SMPL_NEUTRAL.pkl (fetch from https://smpl.is.tue.mpg.de after accepting the license).")
    actions: List[HMR2HumanMeshRecoveryModelActionConfig] = Field(default_factory=list, description="Actions this human-mesh-recovery component exposes to workflows.")

    @model_validator(mode="before")
    def inflate_model(cls, values: Dict[str, Any]):
        if values.get("model") is None:
            values["model"] = {
                "provider": ModelProvider.LOCAL,
                "url": _DEFAULT_MODEL_URL,
                "bundled": True,
            }
        return values

    @model_validator(mode="before")
    def inflate_smpl_model(cls, values: Dict[str, Any]):
        smpl_model = values.get("smpl_model")
        if isinstance(smpl_model, str):
            values["smpl_model"] = { "provider": ModelProvider.LOCAL, "path": smpl_model }
        return values
