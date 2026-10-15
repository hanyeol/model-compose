from typing import Type, Literal, Optional, Dict, List, Set, Annotated, Callable, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.component import ShellComponentConfig, ShellDriverType
from mindor.dsl.schema.action import ShellActionConfig
from mindor.core.foundation import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class ShellDriver(ComponentDriver):
    def __init__(self, id: str, config: ShellComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: ShellComponentConfig = config

    async def run(self, action: ShellActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: ShellActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_shell_driver(driver: ShellDriverType):
    def decorator(cls: Type[ShellDriver]) -> Type[ShellDriver]:
        ShellDriverRegistry[driver] = cls
        return cls
    return decorator

ShellDriverRegistry: Dict[ShellDriverType, Type[ShellDriver]] = {}
