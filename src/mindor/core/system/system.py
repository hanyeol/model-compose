from typing import Optional, Dict
from mindor.dsl.schema.system import SystemConfig
from .base import SystemService, SystemRegistry

SystemInstances: Dict[str, SystemService] = {}

def create_system(id: str, config: SystemConfig, daemon: bool) -> SystemService:
    try:
        system = SystemInstances[id] if id in SystemInstances else None

        if not system:
            if not SystemRegistry:
                from . import services
            system = SystemRegistry[config.type](id, config, daemon)
            SystemInstances[id] = system

        return system
    except KeyError:
        raise ValueError(f"Unsupported system type: {config.type}")
