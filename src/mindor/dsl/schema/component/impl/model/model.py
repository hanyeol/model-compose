from typing import Union, Annotated
from pydantic import Field
from .tasks import *

ModelComponentConfig = Annotated[
    Union[
        TextGenerationModelComponentConfig,
        ChatCompletionModelComponentConfig,
        TextToTextModelComponentConfig,
        TextClassificationModelComponentConfig,
        TextEmbeddingModelComponentConfig,
        ImageToTextModelComponentConfig,
        ImageTextToTextModelComponentConfig,
        ImageGenerationModelComponentConfig,
        ImageUpscaleModelComponentConfig,
        FaceDetectionModelComponentConfig,
        PoseDetectionModelComponentConfig,
        FaceEmbeddingModelComponentConfig,
        TextToSpeechModelComponentConfig,
        SpeechToTextModelComponentConfig,
        MusicGenerationModelComponentConfig
    ],
    Field(discriminator="task")
]
