from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from .impl import *

DatasetsComponentConfig = Annotated[
    Union[
        HuggingfaceDatasetsComponentConfig,
    ],
    Field(discriminator="driver")
]
