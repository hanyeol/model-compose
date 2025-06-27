from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from .impl import *

ListenerConfig = Annotated[
    Union[ 
        HttpCallbackListenerConfig
    ],
    Field(discriminator="type")
]
