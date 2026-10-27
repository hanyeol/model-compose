from typing import Type, Dict, Any
from abc import abstractmethod
from mindor.dsl.schema.component import Model3DLoaderComponentConfig, Model3DLoaderDriverType
from mindor.dsl.schema.action import Model3DLoaderActionConfig
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class Model3DLoaderDriver(ComponentDriver):
    def __init__(self, id: str, config: Model3DLoaderComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: Model3DLoaderComponentConfig = config

    async def run(self, action: Model3DLoaderActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: Model3DLoaderActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_model_3d_loader_driver(driver: Model3DLoaderDriverType):
    def decorator(cls: Type[Model3DLoaderDriver]) -> Type[Model3DLoaderDriver]:
        Model3DLoaderDriverRegistry[driver] = cls
        return cls
    return decorator

Model3DLoaderDriverRegistry: Dict[Model3DLoaderDriverType, Type[Model3DLoaderDriver]] = {}
