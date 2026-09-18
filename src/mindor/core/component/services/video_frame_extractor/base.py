from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.component import VideoFrameExtractorComponentConfig, VideoFrameExtractorDriverType
from mindor.dsl.schema.action import VideoFrameExtractorActionConfig
from mindor.core.foundation import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class VideoFrameExtractorDriver(ComponentDriver):
    def __init__(self, id: str, config: VideoFrameExtractorComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: VideoFrameExtractorComponentConfig = config

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: VideoFrameExtractorActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: VideoFrameExtractorActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_video_frame_extractor_driver(driver: VideoFrameExtractorDriverType):
    def decorator(cls: Type[VideoFrameExtractorDriver]) -> Type[VideoFrameExtractorDriver]:
        VideoFrameExtractorDriverRegistry[driver] = cls
        return cls
    return decorator

VideoFrameExtractorDriverRegistry: Dict[VideoFrameExtractorDriverType, Type[VideoFrameExtractorDriver]] = {}
