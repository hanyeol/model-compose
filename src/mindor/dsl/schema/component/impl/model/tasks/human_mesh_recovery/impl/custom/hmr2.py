from typing import Literal, Union, List, Annotated, Dict, Any
from pydantic import Field, model_validator
from mindor.dsl.schema.action import HMR2HumanMeshRecoveryModelActionConfig
from ..common import CommonHumanMeshRecoveryModelComponentConfig
from .common import HumanMeshRecoveryModelFamily
from ....common import ModelDriverType, ModelProvider, ModelSubmoduleConfig, HuggingfaceModelConfig, LocalModelConfig

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
    smpl: ModelSubmoduleConfig = Field(..., description="SMPL body-model resource (local directory containing the gated SMPL_NEUTRAL.pkl / SMPL_MALE.pkl / SMPL_FEMALE.pkl).")
    actions: List[HMR2HumanMeshRecoveryModelActionConfig] = Field(default_factory=list, description="Actions this human-mesh-recovery component exposes to workflows.")

    @model_validator(mode="before")
    def inflate_model(cls, values: Dict[str, Any]):
        # Fill in the upstream weights tarball when the user hasn't provided a
        # `model` block. `LocalModelConfig.apply_default_path` then derives the
        # extracted directory path under `~/.cache/models/hmr2/`.
        if values.get("model") is None:
            values["model"] = {
                "provider": ModelProvider.LOCAL,
                "url": _DEFAULT_MODEL_URL,
                "bundled": True,
            }
        return values
