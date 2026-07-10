from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.component import ComponentConfig, ComponentType
from .base import ComponentService, ComponentGlobalConfigs, ComponentRegistry, ActionResolver
import importlib

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
                raise LookupError(f"Component not found: {component_id}")
            else:
                return None, None

        return component.id, component

def create_component(id: str, config: ComponentConfig, global_configs: ComponentGlobalConfigs, daemon: bool) -> ComponentService:
    try:
        component = ComponentInstances[id] if id in ComponentInstances else None

        if not component:
            if config.type not in ComponentRegistry:
                _load_component_module(config.type)
            component = ComponentRegistry[config.type](id, config, global_configs, daemon)
            ComponentInstances[id] = component

        return component
    except KeyError:
        raise ValueError(f"Unsupported component type: {config.type}")

def _load_component_module(type: ComponentType) -> None:
    """Import the module that registers the given component type.

    Convention: a component type "foo-bar" (ComponentType.value) maps to
    mindor.core.component.services.foo_bar — either a single-file module
    (foo_bar.py) or a package (foo_bar/__init__.py). Importing the module
    triggers its @register_component decorator, populating ComponentRegistry.
    """
    module_name = type.value.replace("-", "_")
    try:
        importlib.import_module(f"mindor.core.component.services.{module_name}")
    except ImportError as e:
        raise ValueError(f"Unsupported component type: {type}") from e
