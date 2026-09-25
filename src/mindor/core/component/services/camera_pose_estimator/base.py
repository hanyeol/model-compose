from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import CameraPoseEstimatorComponentConfig, CameraPoseEstimatorDriverType
from mindor.dsl.schema.action import CameraPoseEstimatorActionConfig
from mindor.core.foundation import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class CameraPoseEstimatorDriver(ComponentDriver):
    def __init__(self, id: str, config: CameraPoseEstimatorComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: CameraPoseEstimatorComponentConfig = config

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: CameraPoseEstimatorActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: CameraPoseEstimatorActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_camera_pose_estimator_driver(driver: CameraPoseEstimatorDriverType):
    def decorator(cls: Type[CameraPoseEstimatorDriver]) -> Type[CameraPoseEstimatorDriver]:
        CameraPoseEstimatorDriverRegistry[driver] = cls
        return cls
    return decorator

CameraPoseEstimatorDriverRegistry: Dict[CameraPoseEstimatorDriverType, Type[CameraPoseEstimatorDriver]] = {}
