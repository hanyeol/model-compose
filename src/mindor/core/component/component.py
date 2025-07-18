from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.component import ComponentConfig
from .base import ComponentService, ComponentGlobalConfigs, ComponentRegistry

ComponentInstances: Dict[str, ComponentService] = {}

class ComponentResolver:
    def __init__(self, components: Dict[str, ComponentConfig]):
        self.components: Dict[str, ComponentConfig] = components

    def resolve(self, component_id: Optional[str]) -> Tuple[str, ComponentConfig]:
        component_id = component_id or self._find_default_id(self.components)

        if not component_id in self.components:
            raise ValueError(f"Component not found: {component_id}")

        return component_id, self.components[component_id]

    def _find_default_id(self, components: Dict[str, ComponentConfig]) -> str:
        default_ids = [ component_id for component_id, component in components.items() if component.default ]

        if len(default_ids) > 1:
            raise ValueError("Multiple components have default: true")

        if not default_ids and "__default__" not in components:
            raise ValueError("No default component defined.")

        return default_ids[0] if default_ids else "__default__"

def create_component(id: str, config: ComponentConfig, global_configs: ComponentGlobalConfigs, daemon: bool) -> ComponentService:
    try:
        component = ComponentInstances[id] if id in ComponentInstances else None

        if not component:
            if not ComponentRegistry:
                from . import services
            component = ComponentRegistry[config.type](id, config, global_configs, daemon)
            ComponentInstances[id] = component

        return component
    except KeyError:
        raise ValueError(f"Unsupported component type: {config.type}")
