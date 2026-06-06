from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Iterator, Any
from mindor.dsl.schema.logger import ConsoleLoggerConfig
from ..base import LoggerService, LoggerType, LoggingLevel, register_logger
from uvicorn.logging import ColourizedFormatter
import logging, sys

_LEVEL_MAP = {
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
        self.logger.setLevel(_LEVEL_MAP[self.config.level])
        self.logger.propagate = False

    async def _start(self) -> None:
        self.handler = logging.StreamHandler()
        self.handler.setFormatter(self.formatter)
        self.logger.addHandler(self.handler)
        await super()._start()

    async def _stop(self) -> None:
        await super()._stop()
        self.logger.removeHandler(self.handler)
        self.handler = None

    def log(self, level: LoggingLevel, message: str, *args, **kwargs) -> None:
        self.logger.log(_LEVEL_MAP[level], message, *args, **kwargs)
