from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import HMR2HumanMeshRecoveryModelActionConfig
from ..common import CommonHumanMeshRecoveryModelComponentConfig
from .common import HumanMeshRecoveryModelFamily
from ....common import ModelDriverType, ModelSubmoduleConfig

class HMR2HumanMeshRecoveryModelComponentConfig(CommonHumanMeshRecoveryModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[HumanMeshRecoveryModelFamily.HMR2]
    smpl: ModelSubmoduleConfig = Field(..., description="SMPL body-model resource (local directory containing the gated SMPL_NEUTRAL.pkl / SMPL_MALE.pkl / SMPL_FEMALE.pkl).")
    actions: List[HMR2HumanMeshRecoveryModelActionConfig] = Field(default_factory=list, description="Actions this human-mesh-recovery component exposes to workflows.")
