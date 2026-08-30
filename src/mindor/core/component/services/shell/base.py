from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.component import ShellComponentConfig, ShellDriver
from mindor.dsl.schema.action import ShellActionConfig
from mindor.core.foundation import AsyncService
from ...context import ComponentActionContext

class ShellService(AsyncService):
    def __init__(self, id: str, config: ShellComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: ShellComponentConfig = config

    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: ShellActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: ShellActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_shell_service(driver: ShellDriver):
    def decorator(cls: Type[ShellService]) -> Type[ShellService]:
        ShellServiceRegistry[driver] = cls
        return cls
    return decorator

ShellServiceRegistry: Dict[ShellDriver, Type[ShellService]] = {}
