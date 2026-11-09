from typing import Literal, List, Dict, Any
from pydantic import Field, model_validator
from mindor.dsl.schema.action import GVHMRHumanMeshRecoveryModelActionConfig
from ....common import ModelDriverType, ModelProvider, LocalModelConfig
from ..common import CommonHumanMeshRecoveryModelComponentConfig
from .common import HumanMeshRecoveryModelFamily

class GVHMRHumanMeshRecoveryModelComponentConfig(CommonHumanMeshRecoveryModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[HumanMeshRecoveryModelFamily.GVHMR]
    smplx_model: LocalModelConfig = Field(..., description="Local directory containing the gated SMPLX_NEUTRAL.npz (fetch from https://smpl-x.is.tue.mpg.de after accepting the license).")
    actions: List[GVHMRHumanMeshRecoveryModelActionConfig] = Field(default_factory=list, description="Actions this human-mesh-recovery component exposes to workflows.")

    @model_validator(mode="before")
    def inflate_smplx_model(cls, values: Dict[str, Any]):
        smplx_model = values.get("smplx_model")
        if isinstance(smplx_model, str):
            values["smplx_model"] = { "provider": ModelProvider.LOCAL, "path": smplx_model }
        return values
