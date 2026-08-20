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
    TextToVideoModelActionConfig,
    ImageToVideoModelActionConfig,
    ObjectDetectionModelActionConfig,
    FaceDetectionModelActionConfig,
    PoseDetectionModelActionConfig,
    PoseTrackingModelActionConfig,
    FaceEmbeddingModelActionConfig,
    FaceTrackingModelActionConfig,
    TextToSpeechModelActionConfig,
    SpeechToTextModelActionConfig,
    MusicGenerationModelActionConfig,
]
