from __future__ import annotations
from typing import TYPE_CHECKING, Dict, Type
from mindor.dsl.schema.controller import ControllerAdapterConfig, ControllerAdapterType
from mindor.core.foundation import AsyncService

if TYPE_CHECKING:
    from mindor.core.controller.base import ControllerService

class ControllerAdapterService(AsyncService):
    def __init__(self, config: ControllerAdapterConfig, controller: "ControllerService", daemon: bool):
        super().__init__(daemon)
        self.config: ControllerAdapterConfig = config
        self.controller: "ControllerService" = controller

def register_controller_adapter(type: ControllerAdapterType):
    def decorator(cls: Type[ControllerAdapterService]) -> Type[ControllerAdapterService]:
        ControllerAdapterRegistry[type] = cls
        return cls
    return decorator

ControllerAdapterRegistry: Dict[ControllerAdapterType, Type[ControllerAdapterService]] = {}
