from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Iterator, Any
from mindor.dsl.schema.logger import FileLoggerConfig
from ..base import LoggerService, LoggerType, LoggingLevel, register_logger

@register_logger(LoggerType.FILE)
class FileLogger(LoggerService):
    def __init__(self, id: str, config: FileLoggerConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _serve(self) -> None:
        pass

    async def _shutdown(self) -> None:
        pass

    def log(self, level: LoggingLevel, message: str, *args, **kwargs) -> None:
        pass
