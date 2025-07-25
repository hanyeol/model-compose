from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from .impl import *

RuntimeConfig = Annotated[ 
    Union[
        NativeRuntimeConfig,
        DockerRuntimeConfig 
    ],
    Field(discriminator="type")
]
