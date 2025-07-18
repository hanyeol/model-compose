from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.listener import ListenerConfig
from .base import ListenerService, ListenerRegistry

ListenerInstances: Dict[str, ListenerService] = {}

def create_listener(id: str, config: ListenerConfig, daemon: bool) -> ListenerService:
    try:
        listener = ListenerInstances[id] if id in ListenerInstances else None

        if not listener:
            if not ListenerService:
                from . import services
            listener = ListenerRegistry[config.type](id, config, daemon)
            ListenerInstances[id] = listener

        return listener
    except KeyError:
        raise ValueError(f"Unsupported listener type: {config.type}")
