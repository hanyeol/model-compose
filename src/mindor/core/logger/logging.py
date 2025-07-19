from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from .logger import LoggerInstances, LoggingLevel

def debug(message: str, *args, **kwargs) -> None:
    for logger in LoggerInstances.values():
        logger.log(LoggingLevel.DEBUG, message, *args, **kwargs)

def info(message: str, *args, **kwargs) -> None:
    for logger in LoggerInstances.values():
        logger.log(LoggingLevel.INFO, message, *args, **kwargs)

def warning(message: str, *args, **kwargs) -> None:
    for logger in LoggerInstances.values():
        logger.log(LoggingLevel.WARNING, message, *args, **kwargs)

def error(message: str, *args, **kwargs) -> None:
    for logger in LoggerInstances.values():
        logger.log(LoggingLevel.ERROR, message, *args, **kwargs)

def critical(message: str, *args, **kwargs) -> None:
    for logger in LoggerInstances.values():
        logger.log(LoggingLevel.CRITICAL, message, *args, **kwargs)
