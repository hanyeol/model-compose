from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.component import ComponentConfig
from .base import ComponentService, ComponentGlobalConfigs, ComponentRegistry

ComponentInstances: Dict[str, ComponentService] = {}

class ComponentResolver:
    def __init__(self, components: List[ComponentConfig]):
        self.components: List[ComponentConfig] = components

    def resolve(self, component_id: Optional[str]) -> Tuple[str, ComponentConfig]:
        component_id = component_id or self._find_default_id(self.components)
        component = next((component for component in self.components if component.id == component_id), None)

        if component is None:
            raise ValueError(f"Component not found: {component_id}")

        return component_id, component

    def _find_default_id(self, components: List[ComponentConfig]) -> str:
        default_ids = [ component.id for component in components if component.default or component.id == "__default__" ]

        if len(default_ids) > 1:
            raise ValueError("Multiple components have default: true")

        if not default_ids:
            raise ValueError("No default component defined.")

        return default_ids[0]

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
