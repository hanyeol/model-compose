from typing import Union, Annotated
from pydantic import Field
from .impl import *

TextGenerationModelComponentConfig = Annotated[
    Union[
        HuggingfaceTextGenerationModelComponentConfig,
        LlamaCppTextGenerationModelComponentConfig,
        VllmTextGenerationModelComponentConfig,
        CustomTextGenerationModelComponentConfig,
    ],
    Field(discriminator="driver")
]
