from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from .impl import *

JobConfig = Annotated[
    Union[ 
        ActionJobConfig,
        DelayJobConfig,
        IfJobConfig,
        SwitchJobConfig,
        RandomRouterJobConfig,
        FilterJobConfig
    ],
    Field(discriminator="type")
]
