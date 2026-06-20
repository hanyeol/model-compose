from typing import Union, Annotated
from pydantic import Field
from .impl import *

ModelComponentConfig = Annotated[
    Union[
        TextGenerationModelComponentConfig,
        ChatCompletionModelComponentConfig,
        TextClassificationModelComponentConfig,
        TextEmbeddingModelComponentConfig,
        ImageToTextModelComponentConfig,
        ImageGenerationModelComponentConfig,
        ImageUpscaleModelComponentConfig,
        FaceDetectionModelComponentConfig,
        FaceEmbeddingModelComponentConfig,
        TextToSpeechModelComponentConfig,
        SpeechToTextModelComponentConfig,
        MusicGenerationModelComponentConfig
    ],
    Field(discriminator="task")
]
