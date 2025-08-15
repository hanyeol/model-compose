from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator

class HttpStreamFormat(str, Enum):
    JSON = "json"
    TEXT = "text"
