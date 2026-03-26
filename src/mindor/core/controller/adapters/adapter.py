from __future__ import annotations
from typing import TYPE_CHECKING

from mindor.dsl.schema.controller import ControllerAdapterConfig
from .base import ControllerAdapterService, ControllerAdapterRegistry

if TYPE_CHECKING:
    from mindor.core.controller.base import ControllerService

def create_controller_adapter(config: ControllerAdapterConfig, controller: ControllerService, daemon: bool) -> ControllerAdapterService:
    if not ControllerAdapterRegistry:
        from . import services
    try:
        return ControllerAdapterRegistry[config.type](config, controller, daemon)
    except KeyError:
        raise ValueError(f"Unsupported controller adapter type: {config.type}")
