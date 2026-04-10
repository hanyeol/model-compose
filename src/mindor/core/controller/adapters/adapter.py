from __future__ import annotations
from typing import TYPE_CHECKING, Dict

from mindor.dsl.schema.controller import ControllerAdapterConfig
from .base import ControllerAdapterService, ControllerAdapterRegistry

if TYPE_CHECKING:
    from mindor.core.controller.base import ControllerService

AdapterInstances: Dict[str, ControllerAdapterService] = {}

def create_controller_adapter(config: ControllerAdapterConfig, controller: ControllerService, daemon: bool) -> ControllerAdapterService:
    try:
        adapter = AdapterInstances.get(config.type)

        if not adapter:
            if not ControllerAdapterRegistry:
                from . import services
            adapter = ControllerAdapterRegistry[config.type](config, controller, daemon)
            AdapterInstances[config.type] = adapter

        return adapter
    except KeyError:
        raise ValueError(f"Unsupported controller adapter type: {config.type}")
