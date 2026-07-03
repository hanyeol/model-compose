from typing import Union
from .impl import *

ModelActionConfig = Union[
    TextGenerationModelActionConfig,
    ChatCompletionModelActionConfig,
    TextClassificationModelActionConfig,
    TextEmbeddingModelActionConfig,
    ImageToTextModelActionConfig,
    ImageTextToTextModelActionConfig,
    TextToImageModelActionConfig,
    ImageUpscaleModelActionConfig,
    FaceDetectionModelActionConfig,
    PoseDetectionModelActionConfig,
    FaceEmbeddingModelActionConfig,
    TextToSpeechModelActionConfig,
    SpeechToTextModelActionConfig,
    MusicGenerationModelActionConfig,
]
