from typing import Union
from pydantic import Field, model_validator
from ..common import CommonFaceDetectionModelActionConfig, CommonFaceDetectionParamsConfig

class YoloFaceDetectionParamsConfig(CommonFaceDetectionParamsConfig):
    detection_size: Union[int, str] = Field(default=640, description="Detector input resolution in pixels; the longer image side is resized to this length.")
    iou_threshold: Union[float, str] = Field(default=0.45, description="IoU threshold used by non-maximum suppression when merging overlapping boxes.")
    max_num_faces: Union[int, str] = Field(default=0, description="Maximum number of faces detected per image; 0 means unbounded.")

class YoloFaceDetectionModelActionConfig(CommonFaceDetectionModelActionConfig):
    params: YoloFaceDetectionParamsConfig = Field(default_factory=YoloFaceDetectionParamsConfig, description="YOLO-specific face detection parameters.")

    @model_validator(mode="after")
    def reject_landmarks(self):
        if self.return_landmarks is True:
            raise ValueError("'return_landmarks' is not supported by the YOLO face detector; it emits bounding boxes only.")
        return self
