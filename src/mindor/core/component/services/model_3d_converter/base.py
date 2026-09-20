from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import Model3DConverterComponentConfig, Model3DConverterDriverType
from mindor.dsl.schema.action import Model3DConverterActionConfig
from mindor.core.foundation import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class Model3DConverterDriver(ComponentDriver):
    def __init__(self, id: str, config: Model3DConverterComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: Model3DConverterComponentConfig = config

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: Model3DConverterActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: Model3DConverterActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_model_3d_converter_driver(driver: Model3DConverterDriverType):
    def decorator(cls: Type[Model3DConverterDriver]) -> Type[Model3DConverterDriver]:
        Model3DConverterDriverRegistry[driver] = cls
        return cls
    return decorator

Model3DConverterDriverRegistry: Dict[Model3DConverterDriverType, Type[Model3DConverterDriver]] = {}
