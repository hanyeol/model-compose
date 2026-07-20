from typing import Union
from .tasks import *

ModelActionConfig = Union[
    TextGenerationModelActionConfig,
    ChatCompletionModelActionConfig,
    TextToTextModelActionConfig,
    TextClassificationModelActionConfig,
    TextEmbeddingModelActionConfig,
    TextRerankingModelActionConfig,
    ImageToTextModelActionConfig,
    ImageTextToTextModelActionConfig,
    ImageGenerationModelActionConfig,
    ImageEmbeddingModelActionConfig,
    ImageUpscaleModelActionConfig,
    ImageBackgroundRemovalModelActionConfig,
    ImageSegmentationModelActionConfig,
    ObjectDetectionModelActionConfig,
    FaceDetectionModelActionConfig,
    PoseDetectionModelActionConfig,
    FaceEmbeddingModelActionConfig,
    TextToSpeechModelActionConfig,
    SpeechToTextModelActionConfig,
    MusicGenerationModelActionConfig,
]
