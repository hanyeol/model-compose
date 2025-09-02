from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.component import ComponentConfig
from .base import ComponentService, ComponentGlobalConfigs, ComponentRegistry, ActionResolver

ComponentInstances: Dict[str, ComponentService] = {}

class ComponentResolver:
    def __init__(self, components: List[ComponentConfig]):
        self.components: List[ComponentConfig] = components

    def resolve(self, component_id: str, raise_on_error: bool = True)  -> Union[Tuple[str, ComponentConfig], Tuple[None, None]]:
        if component_id == "__default__":
            component = self.components[0] if len(self.components) == 1 else None
            component = component or next((component for component in self.components if component.default), None)
        else:
            component = next((component for component in self.components if component.id == component_id), None)

        if component is None:
            if raise_on_error:
                raise ValueError(f"Component not found: {component_id}")
            else:
                return None, None

        return component.id, component

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
