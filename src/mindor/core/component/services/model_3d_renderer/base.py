from typing import Type, Optional, Dict, List, Any, Union, Tuple
from abc import abstractmethod
from mindor.dsl.schema.component import Model3DRendererComponentConfig, Model3DRendererDriverType
from mindor.dsl.schema.action import Model3DRendererActionConfig
from mindor.core.foundation import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class Model3DRendererDriver(ComponentDriver):
    def __init__(self, id: str, config: Model3DRendererComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: Model3DRendererComponentConfig = config

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        return None

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
