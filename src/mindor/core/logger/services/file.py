from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Iterator, Any
from mindor.dsl.schema.logger import FileLoggerConfig
from ..base import LoggerService, LoggerType, LoggingLevel, register_logger
from pathlib import Path
import logging

_level_map = {
    LoggingLevel.DEBUG:    logging.DEBUG,
    LoggingLevel.INFO:     logging.INFO,
    LoggingLevel.WARNING:  logging.WARNING,
    LoggingLevel.ERROR:    logging.ERROR,
    LoggingLevel.CRITICAL: logging.CRITICAL,
}

@register_logger(LoggerType.FILE)
class FileLogger(LoggerService):
    def __init__(self, id: str, config: FileLoggerConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.logger: logging.Logger = logging.getLogger(id)
        self.formatter: logging.Formatter = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
        self.handler: logging.FileHandler = None

        self._configure_logger()

    def _configure_logger(self) -> None:
        self.logger.setLevel(_level_map[self.config.level])
        self.logger.propagate = False

    async def _serve(self) -> None:
        Path(self.config.path).parent.mkdir(parents=True, exist_ok=True)
        self.handler = logging.FileHandler(self.config.path, mode="a", encoding="utf-8")
        self.handler.setFormatter(self.formatter)
        self.logger.addHandler(self.handler)

    async def _shutdown(self) -> None:
        self.logger.removeHandler(self.handler)
        self.handler = None

    def log(self, level: LoggingLevel, message: str, *args, **kwargs) -> None:
        self.logger.log(_level_map[level], message, *args, **kwargs)
