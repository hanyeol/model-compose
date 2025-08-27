from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import LoggerType, CommonLoggerConfig

class FileLoggerConfig(CommonLoggerConfig):
    type: Literal[LoggerType.FILE]
    path: str = Field(default="./logs/run.log", description="File path where logs will be written.")
