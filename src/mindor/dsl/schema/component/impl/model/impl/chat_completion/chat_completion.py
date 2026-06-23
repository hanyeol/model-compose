from typing import Union, Annotated
from pydantic import Field
from .impl import *

ChatCompletionModelComponentConfig = Annotated[
    Union[
        HuggingfaceChatCompletionModelComponentConfig,
        LlamaCppChatCompletionModelComponentConfig,
        VllmChatCompletionModelComponentConfig,
        CustomChatCompletionModelComponentConfig,
    ],
    Field(discriminator="driver")
]
