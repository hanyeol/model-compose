from typing import Union, Annotated
from pydantic import Field
from .hmr2 import HMR2HumanMeshRecoveryModelComponentConfig
from .gvhmr import GVHMRHumanMeshRecoveryModelComponentConfig

CustomHumanMeshRecoveryModelComponentConfig = Annotated[
    Union[
        HMR2HumanMeshRecoveryModelComponentConfig,
        GVHMRHumanMeshRecoveryModelComponentConfig,
    ],
    Field(discriminator="family")
]
