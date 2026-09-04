from typing import Union, Dict, Annotated, Any
from pydantic import Field
from ..common import ComponentType, component_validator
from .tasks import *

ModelComponentConfig = Annotated[
    Union[
        TextGenerationModelComponentConfig,
        ChatCompletionModelComponentConfig,
        TextToTextModelComponentConfig,
        TextClassificationModelComponentConfig,
        TextEmbeddingModelComponentConfig,
        TextRerankingModelComponentConfig,
        ImageToTextModelComponentConfig,
        ImageTextToTextModelComponentConfig,
        ImageGenerationModelComponentConfig,
        ImageEmbeddingModelComponentConfig,
        VideoEmbeddingModelComponentConfig,
        ImageUpscaleModelComponentConfig,
        ImageBackgroundRemovalModelComponentConfig,
        ImageSegmentationModelComponentConfig,
        TextToVideoModelComponentConfig,
        ImageToVideoModelComponentConfig,
        ObjectDetectionModelComponentConfig,
        ObjectTrackingModelComponentConfig,
        ShotBoundaryDetectionModelComponentConfig,
        FaceDetectionModelComponentConfig,
        PoseDetectionModelComponentConfig,
        PoseTrackingModelComponentConfig,
        FaceEmbeddingModelComponentConfig,
        FaceTrackingModelComponentConfig,
        FaceSwapModelComponentConfig,
        TextToSpeechModelComponentConfig,
        SpeechToTextModelComponentConfig,
        AudioTextAlignmentModelComponentConfig,
        VoiceActivityDetectionModelComponentConfig,
        SpeakerDiarizationModelComponentConfig,
        MusicGenerationModelComponentConfig,
        MusicSourceSeparationModelComponentConfig,
        MusicTranscriptionModelComponentConfig
    ],
    Field(discriminator="task")
]

@component_validator(ComponentType.MODEL, mode="before")
def inflate_default_driver(values: Dict[str, Any]) -> None:
    if "driver" not in values:
        values["driver"] = ModelDriver.HUGGINGFACE
