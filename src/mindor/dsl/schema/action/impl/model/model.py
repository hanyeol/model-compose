from typing import Union
from .impl import *

ModelActionConfig = Union[
    TextGenerationModelActionConfig,
    ChatCompletionModelActionConfig,
    TextClassificationModelActionConfig,
    TextEmbeddingModelActionConfig,
    ImageToTextModelActionConfig,
    ImageGenerationModelActionConfig,
    ImageUpscaleModelActionConfig,
    FaceEmbeddingModelActionConfig,
    TextToSpeechModelActionConfig,
    SpeechToTextModelActionConfig,
    MusicGenerationModelActionConfig,
]
