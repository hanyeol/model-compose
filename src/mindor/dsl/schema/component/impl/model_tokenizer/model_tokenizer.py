from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from .tasks import *

ModelTokenizerComponentConfig = Annotated[
    Union[
        TextModelTokenizerComponentConfig,
    ],
    Field(discriminator="task")
]
