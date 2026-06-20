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
    FaceDetectionModelActionConfig,
    FaceEmbeddingModelActionConfig,
    TextToSpeechModelActionConfig,
    SpeechToTextModelActionConfig,
    MusicGenerationModelActionConfig,
]
