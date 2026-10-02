from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from .tasks import *

ModelTrainerComponentConfig = Annotated[
    Union[
        SftModelTrainerComponentConfig,
        TextClassificationModelTrainerComponentConfig,
        TypedDecisionModelTrainerComponentConfig,
    ],
    Field(discriminator="task")
]
