from typing import Union, Optional
from pydantic import Field
from mindor.dsl.schema.common.box import Box
from ..common import CommonLipSyncParamsConfig, CommonLipSyncModelActionConfig

class Wav2LipLipSyncParamsConfig(CommonLipSyncParamsConfig):
    resize_factor: Union[int, str] = Field(default=1, description="Downscale factor applied to input frames before inference.")
    frame_crop_box: Optional[Box] = Field(default=None, description="Crop rectangle (left, top, right, bottom) applied to input frames; `null` on any edge keeps the frame edge.")
    face_bounding_box: Optional[Box] = Field(default=None, description="Fixed face bounding box (left, top, right, bottom) that bypasses face detection.")
    face_bounding_box_padding: Box = Field(default=(0, 0, 0, 10), description="Pixel padding (left, top, right, bottom) added around the detected face bounding box.")
    face_detection_batch_size: Union[int, str] = Field(default=16, description="Number of frames processed per face-detection batch.")
    generator_batch_size: Union[int, str] = Field(default=128, description="Number of samples processed per Wav2Lip generator batch.")
    face_smoothing: Union[bool, str] = Field(default=True, description="Whether to apply temporal smoothing to face detections across frames.")
    static: Union[bool, str] = Field(default=False, description="Whether to reuse the first frame as a still image for the entire audio.")

class Wav2LipLipSyncModelActionConfig(CommonLipSyncModelActionConfig):
    params: Wav2LipLipSyncParamsConfig = Field(default_factory=Wav2LipLipSyncParamsConfig, description="Wav2Lip generation parameters.")
