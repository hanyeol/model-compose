from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import SentenceSplitterComponentConfig, SentenceSplitterDriverType
from mindor.dsl.schema.action import SentenceSplitterActionConfig
from mindor.core.foundation import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class SentenceSplitterDriver(ComponentDriver):
    def __init__(self, id: str, config: SentenceSplitterComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: SentenceSplitterComponentConfig = config

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: SentenceSplitterActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: SentenceSplitterActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_sentence_splitter_driver(driver: SentenceSplitterDriverType):
    def decorator(cls: Type[SentenceSplitterDriver]) -> Type[SentenceSplitterDriver]:
        SentenceSplitterDriverRegistry[driver] = cls
        return cls
    return decorator

SentenceSplitterDriverRegistry: Dict[SentenceSplitterDriverType, Type[SentenceSplitterDriver]] = {}
