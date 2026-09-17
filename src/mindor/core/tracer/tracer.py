from typing import Dict
from mindor.dsl.schema.tracer import TracerConfig
from .base import TracerService, TracerRegistry

TracerInstances: Dict[str, TracerService] = {}

def create_tracer(id: str, config: TracerConfig, daemon: bool, cache: bool = True) -> TracerService:
    try:
        tracer = TracerInstances[id] if cache and id in TracerInstances else None

        if not tracer:
            if not TracerRegistry:
                from . import services

            tracer = TracerRegistry[config.driver](id, config, daemon)

            if cache:
                TracerInstances[id] = tracer

        return tracer
    except KeyError:
        raise ValueError(f"Unsupported tracer driver: {config.driver}")
