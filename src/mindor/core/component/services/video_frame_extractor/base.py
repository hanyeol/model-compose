from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.component import VideoFrameExtractorComponentConfig, VideoFrameExtractorDriver
from mindor.dsl.schema.action import VideoFrameExtractorActionConfig
from mindor.core.foundation import AsyncService
from ...context import ComponentActionContext
import asyncio

class VideoFrameExtractorService(AsyncService):
    def __init__(self, id: str, config: VideoFrameExtractorComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: VideoFrameExtractorComponentConfig = config

    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: VideoFrameExtractorActionConfig, context: ComponentActionContext) -> Any:
        return await self.run_in_thread(self._run, action, context, asyncio.get_running_loop())

    @abstractmethod
    async def _run(self, action: VideoFrameExtractorActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        pass

def register_video_frame_extractor_service(driver: VideoFrameExtractorDriver):
    def decorator(cls: Type[VideoFrameExtractorService]) -> Type[VideoFrameExtractorService]:
        VideoFrameExtractorServiceRegistry[driver] = cls
        return cls
    return decorator

VideoFrameExtractorServiceRegistry: Dict[VideoFrameExtractorDriver, Type[VideoFrameExtractorService]] = {}
