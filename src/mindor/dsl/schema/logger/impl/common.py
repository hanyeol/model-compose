from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from .types import LoggerType

class LoggingLevel(str, Enum):
    DEBUG    = "debug"
    INFO     = "info"
    WARNING  = "warning"
    ERROR    = "error"
    CRITICAL = "critical"

class CommonLoggerConfig(BaseModel):
    type: LoggerType = Field(..., description="Type of logger.")
    level: LoggingLevel = Field(default=LoggingLevel.INFO, description="Minimum logging level to capture.")
