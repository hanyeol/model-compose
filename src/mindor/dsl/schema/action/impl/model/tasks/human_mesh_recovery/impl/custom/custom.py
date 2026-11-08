from typing import Union
from .hmr2 import HMR2HumanMeshRecoveryModelActionConfig
from .gvhmr import GVHMRHumanMeshRecoveryModelActionConfig

CustomHumanMeshRecoveryModelActionConfig = Union[
    HMR2HumanMeshRecoveryModelActionConfig,
    GVHMRHumanMeshRecoveryModelActionConfig,
]
