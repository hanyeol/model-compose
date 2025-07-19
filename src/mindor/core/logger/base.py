from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.logger import LoggerConfig, LoggerType, LoggingLevel
from mindor.core.services import AsyncService

class LoggerService(AsyncService):
    def __init__(self, id: str, config: LoggerConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: LoggerConfig = config

    @abstractmethod
    def log(self, level: LoggingLevel, message: str, *args, **kwargs) -> None:
        pass

def register_logger(type: LoggerType):
    def decorator(cls: Type[LoggerService]) -> Type[LoggerService]:
        LoggerRegistry[type] = cls
        return cls
    return decorator

LoggerRegistry: Dict[LoggerType, Type[LoggerService]] = {}
