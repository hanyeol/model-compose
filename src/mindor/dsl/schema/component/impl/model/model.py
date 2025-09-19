from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from .tasks import *

ModelComponentConfig = Annotated[
    Union[ 
        TextGenerationModelComponentConfig,
        ChatCompletionModelComponentConfig,
        TextClassificationModelComponentConfig,
        TextEmbeddingModelComponentConfig,
        ImageToTextModelComponentConfig,
        ImageGenerationModelComponentConfig,
        ImageUpscaleModelComponentConfig,
    ],
    Field(discriminator="task")
]
