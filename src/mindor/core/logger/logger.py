from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from mindor.dsl.schema.logger import LoggerConfig
from .base import LoggerService, LoggerRegistry, LoggingLevel

LoggerInstances: Dict[str, LoggerService] = {}

def create_logger(id: str, config: LoggerConfig, daemon: bool) -> LoggerService:
    try:
        logger = LoggerInstances[id] if id in LoggerInstances else None

        if not logger:
            if not LoggerRegistry:
                from . import services
            logger = LoggerRegistry[config.type](id, config, daemon)
            LoggerInstances[id] = logger

        return logger
    except KeyError:
        raise ValueError(f"Unsupported logger type: {config.type}")
