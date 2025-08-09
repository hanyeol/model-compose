from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from .impl import *

ModelComponentConfig = Annotated[
    Union[ 
        TextGenerationModelComponentConfig,
        SummarizationModelComponentConfig,
        TranslationModelComponentConfig,
        TextClassificationModelComponentConfig,
        TextEmbeddingModelComponentConfig,
        ImageToTextModelComponentConfig,
    ],
    Field(discriminator="task")
]
