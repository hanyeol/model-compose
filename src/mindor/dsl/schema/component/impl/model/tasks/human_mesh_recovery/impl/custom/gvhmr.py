from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import GVHMRHumanMeshRecoveryModelActionConfig
from ..common import CommonHumanMeshRecoveryModelComponentConfig
from .common import HumanMeshRecoveryModelFamily
from ....common import ModelDriverType, ModelSubmoduleConfig

class GVHMRHumanMeshRecoveryModelComponentConfig(CommonHumanMeshRecoveryModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[HumanMeshRecoveryModelFamily.GVHMR]
    smplx: ModelSubmoduleConfig = Field(..., description="SMPL-X body-model resource (local directory containing the gated SMPLX_NEUTRAL.npz).")
    actions: List[GVHMRHumanMeshRecoveryModelActionConfig] = Field(default_factory=list, description="Actions this human-mesh-recovery component exposes to workflows.")
