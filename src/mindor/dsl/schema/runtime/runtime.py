from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from .impl import *

class RuntimeType(str, Enum):
    DOCKER = "docker"
    NATIVE = "native"

RuntimeConfig = Annotated[ 
    Union[ 
        DockerRuntimeConfig 
    ],
    Field(discriminator="type")
]
