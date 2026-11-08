from mindor.dsl.schema.component import ModelComponentConfig, HumanMeshRecoveryModelFamily
from ....base import ModelTaskType, ModelDriverType, register_model_task_driver

@register_model_task_driver(ModelTaskType.HUMAN_MESH_RECOVERY, ModelDriverType.CUSTOM)
class CustomHumanMeshRecoveryTaskDriver:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == HumanMeshRecoveryModelFamily.HMR2:
            from .hmr2 import HMR2HumanMeshRecoveryTaskDriver
            return HMR2HumanMeshRecoveryTaskDriver(id, config, daemon)

        if config.family == HumanMeshRecoveryModelFamily.GVHMR:
            from .gvhmr import GVHMRHumanMeshRecoveryTaskDriver
            return GVHMRHumanMeshRecoveryTaskDriver(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
