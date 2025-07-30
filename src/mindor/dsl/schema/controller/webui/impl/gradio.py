from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from .common import CommonWebUIConfig, ControllerWebUIDriver

class GradioWebUIConfig(CommonWebUIConfig):
    driver: Literal[ControllerWebUIDriver.GRADIO]
