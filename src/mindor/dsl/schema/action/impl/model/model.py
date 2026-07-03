from typing import Union
from .tasks import *

ModelActionConfig = Union[
    TextGenerationModelActionConfig,
    ChatCompletionModelActionConfig,
    TextToTextModelActionConfig,
    TextClassificationModelActionConfig,
    TextEmbeddingModelActionConfig,
    ImageToTextModelActionConfig,
    ImageTextToTextModelActionConfig,
    ImageGenerationModelActionConfig,
    ImageUpscaleModelActionConfig,
    FaceDetectionModelActionConfig,
    PoseDetectionModelActionConfig,
    FaceEmbeddingModelActionConfig,
    TextToSpeechModelActionConfig,
    SpeechToTextModelActionConfig,
    MusicGenerationModelActionConfig,
]
