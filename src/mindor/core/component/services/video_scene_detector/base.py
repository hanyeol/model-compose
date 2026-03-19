from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.component import VideoSceneDetectorComponentConfig, VideoSceneDetectorDriver
from mindor.dsl.schema.action import VideoSceneDetectorActionConfig
from mindor.core.foundation import AsyncService
from ...context import ComponentActionContext

class VideoSceneDetectorService(AsyncService):
    def __init__(self, id: str, config: VideoSceneDetectorComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: VideoSceneDetectorComponentConfig = config

    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: VideoSceneDetectorActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    async def _serve(self) -> None:
        pass

    async def _shutdown(self) -> None:
        pass

    @abstractmethod
    async def _run(self, action: VideoSceneDetectorActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_video_scene_detector_service(driver: VideoSceneDetectorDriver):
    def decorator(cls: Type[VideoSceneDetectorService]) -> Type[VideoSceneDetectorService]:
        VideoSceneDetectorServiceRegistry[driver] = cls
        return cls
    return decorator

VideoSceneDetectorServiceRegistry: Dict[VideoSceneDetectorDriver, Type[VideoSceneDetectorService]] = {}
