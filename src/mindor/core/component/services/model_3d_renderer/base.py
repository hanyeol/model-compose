from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import Model3DRendererComponentConfig, Model3DRendererDriverType
from mindor.dsl.schema.action import Model3DRendererActionConfig
from mindor.core.foundation.async_service import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class Model3DRendererDriver(ComponentDriver):
    config: Model3DRendererComponentConfig

    async def run(self, action: Model3DRendererActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: Model3DRendererActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_model_3d_renderer_driver(driver: Model3DRendererDriverType):
    def decorator(cls: Type[Model3DRendererDriver]) -> Type[Model3DRendererDriver]:
        Model3DRendererDriverRegistry[driver] = cls
        return cls
    return decorator

Model3DRendererDriverRegistry: Dict[Model3DRendererDriverType, Type[Model3DRendererDriver]] = {}
