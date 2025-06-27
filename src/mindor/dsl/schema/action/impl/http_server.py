from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonActionConfig

class HttpServerActionConfig(CommonActionConfig):
    path: Optional[str] = None
    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH"] = "POST"
