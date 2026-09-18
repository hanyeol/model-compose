from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.component import DatasetsComponentConfig, DatasetsDriverType
from mindor.dsl.schema.action import DatasetsActionConfig
from mindor.core.foundation import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class DatasetsDriver(ComponentDriver):
    def __init__(self, id: str, config: DatasetsComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: DatasetsComponentConfig = config

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: DatasetsActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: DatasetsActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_datasets_driver(driver: DatasetsDriverType):
    def decorator(cls: Type[DatasetsDriver]) -> Type[DatasetsDriver]:
        DatasetsDriverRegistry[driver] = cls
        return cls
    return decorator

DatasetsDriverRegistry: Dict[DatasetsDriverType, Type[DatasetsDriver]] = {}
