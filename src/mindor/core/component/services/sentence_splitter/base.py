from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import SentenceSplitterComponentConfig, SentenceSplitterDriver
from mindor.dsl.schema.action import SentenceSplitterActionConfig
from mindor.core.foundation import AsyncService
from ...context import ComponentActionContext
import asyncio

class SentenceSplitterService(AsyncService):
    def __init__(self, id: str, config: SentenceSplitterComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: SentenceSplitterComponentConfig = config

    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: SentenceSplitterActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context, asyncio.get_running_loop())

    @abstractmethod
    async def _run(self, action: SentenceSplitterActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        pass

def register_sentence_splitter_service(driver: SentenceSplitterDriver):
    def decorator(cls: Type[SentenceSplitterService]) -> Type[SentenceSplitterService]:
        SentenceSplitterServiceRegistry[driver] = cls
        return cls
    return decorator

SentenceSplitterServiceRegistry: Dict[SentenceSplitterDriver, Type[SentenceSplitterService]] = {}
