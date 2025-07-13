from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.listener import ListenerConfig
from .base import ListenerEngine, ListenerRegistry

ListenerInstances: Dict[str, ListenerEngine] = {}

def create_listener(id: str, config: ListenerConfig, daemon: bool) -> ListenerEngine:
    try:
        listener = ListenerInstances[id] if id in ListenerInstances else None

        if not listener:
            if not ListenerEngine:
                from . import engine
            listener = ListenerRegistry[config.type](id, config, daemon)
            ListenerInstances[id] = listener

        return listener
    except KeyError:
        raise ValueError(f"Unsupported listener type: {config.type}")
