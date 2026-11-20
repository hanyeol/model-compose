from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import VideoMotionEstimatorComponentConfig, VideoMotionEstimatorDriverType
from mindor.dsl.schema.action import VideoMotionEstimatorActionConfig
from mindor.core.foundation.async_service import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class VideoMotionEstimatorDriver(ComponentDriver):
    config: VideoMotionEstimatorComponentConfig

    async def run(self, action: VideoMotionEstimatorActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: VideoMotionEstimatorActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_video_motion_estimator_driver(driver: VideoMotionEstimatorDriverType):
    def decorator(cls: Type[VideoMotionEstimatorDriver]) -> Type[VideoMotionEstimatorDriver]:
        VideoMotionEstimatorDriverRegistry[driver] = cls
        return cls
    return decorator

VideoMotionEstimatorDriverRegistry: Dict[VideoMotionEstimatorDriverType, Type[VideoMotionEstimatorDriver]] = {}
