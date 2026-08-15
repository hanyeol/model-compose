from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import MediaDownloaderComponentConfig, MediaDownloaderDriver
from mindor.dsl.schema.action import MediaDownloaderActionConfig
from mindor.core.foundation import AsyncService
from ...context import ComponentActionContext

class MediaDownloaderService(AsyncService):
    def __init__(self, id: str, config: MediaDownloaderComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: MediaDownloaderComponentConfig = config

    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: MediaDownloaderActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: MediaDownloaderActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_media_downloader_service(driver: MediaDownloaderDriver):
    def decorator(cls: Type[MediaDownloaderService]) -> Type[MediaDownloaderService]:
        MediaDownloaderServiceRegistry[driver] = cls
        return cls
    return decorator

MediaDownloaderServiceRegistry: Dict[MediaDownloaderDriver, Type[MediaDownloaderService]] = {}
