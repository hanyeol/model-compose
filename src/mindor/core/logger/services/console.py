from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Iterator, Any
from mindor.dsl.schema.logger import ConsoleLoggerConfig
from ..base import LoggerService, LoggerType, LoggingLevel, register_logger
from uvicorn.logging import ColourizedFormatter
import logging, sys

_level_map = {
    LoggingLevel.DEBUG:    logging.DEBUG,
    LoggingLevel.INFO:     logging.INFO,
    LoggingLevel.WARNING:  logging.WARNING,
    LoggingLevel.ERROR:    logging.ERROR,
    LoggingLevel.CRITICAL: logging.CRITICAL,
}

@register_logger(LoggerType.CONSOLE)
class ConsoleLogger(LoggerService):
    def __init__(self, id: str, config: ConsoleLoggerConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.logger: logging.Logger = logging.getLogger(id)
        self.formatter: logging.Formatter = ColourizedFormatter("%(levelprefix)s %(message)s")
        self.handler: logging.StreamHandler = None

        self._configure_logger()

    def _configure_logger(self) -> None:
        self.logger.setLevel(_level_map[self.config.level])
        self.logger.propagate = False

    async def _serve(self) -> None:
        self.handler = logging.StreamHandler()
        self.handler.setFormatter(self.formatter)
        self.logger.addHandler(self.handler)

    async def _shutdown(self) -> None:
        self.logger.removeHandler(self.handler)
        self.handler = None

    def log(self, level: LoggingLevel, message: str, *args, **kwargs) -> None:
        self.logger.log(_level_map[level], message, *args, **kwargs)
