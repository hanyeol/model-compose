from typing import Literal
from ...common import CommonModelComponentConfig, ModelTaskType

class CommonHumanMeshRecoveryModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.HUMAN_MESH_RECOVERY]
