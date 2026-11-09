from typing import Literal, Union, List, Annotated, Dict, Any
from pydantic import Field, model_validator
from mindor.dsl.schema.action import GVHMRHumanMeshRecoveryModelActionConfig
from ....common import ModelDriverType, ModelProvider, HuggingfaceModelConfig, LocalModelConfig
from ..common import CommonHumanMeshRecoveryModelComponentConfig
from .common import HumanMeshRecoveryModelFamily

# Upstream zju3dv distributes GVHMR checkpoints only through Google Drive; the
# ryanrudes/gvhmr HF repo is a packaged release that includes the model card and
# a weight bundle. `camenduru/GVHMR` is the older community mirror the ryanrudes
# package falls back to, and preserves the same on-disk layout (gvhmr/, hmr2/,
# vitpose/, yolo/, dpvo/). Default to it so the driver works out of the box with
# no HF auth.
_DEFAULT_MODEL_REPOSITORY = "camenduru/GVHMR"

GVHMRHumanMeshRecoveryModelConfig = Annotated[
    Union[
        HuggingfaceModelConfig,
        LocalModelConfig,
    ],
    Field(discriminator="provider")
]

class GVHMRHumanMeshRecoveryModelComponentConfig(CommonHumanMeshRecoveryModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[HumanMeshRecoveryModelFamily.GVHMR]
    model: GVHMRHumanMeshRecoveryModelConfig = Field(..., description="GVHMR checkpoint bundle — defaults to the camenduru/GVHMR HuggingFace mirror when omitted.")
    smplx_model: LocalModelConfig = Field(..., description="Local directory containing the gated SMPLX_NEUTRAL.npz (fetch from https://smpl-x.is.tue.mpg.de after accepting the license).")
    actions: List[GVHMRHumanMeshRecoveryModelActionConfig] = Field(default_factory=list, description="Actions this human-mesh-recovery component exposes to workflows.")

    @model_validator(mode="before")
    def inflate_model(cls, values: Dict[str, Any]):
        if values.get("model") is None:
            values["model"] = {
                "provider": ModelProvider.HUGGINGFACE,
                "repository": _DEFAULT_MODEL_REPOSITORY,
            }
        return values

    @model_validator(mode="before")
    def inflate_smplx_model(cls, values: Dict[str, Any]):
        smplx_model = values.get("smplx_model")
        if isinstance(smplx_model, str):
            values["smplx_model"] = { "provider": ModelProvider.LOCAL, "path": smplx_model }
        return values
