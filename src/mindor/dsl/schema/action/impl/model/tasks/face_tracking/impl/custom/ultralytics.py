from typing import Literal, Union
from pydantic import Field, model_validator
from ..common import CommonFaceTrackingModelActionConfig, CommonFaceTrackingParamsConfig

class YoloFaceTrackingParamsConfig(CommonFaceTrackingParamsConfig):
    min_confidence: Union[float, str] = Field(default=0.5, description="Minimum detection confidence a face must reach, from 0.0 to 1.0.")
    detection_size: Union[int, str] = Field(default=640, description="Detector input resolution in pixels; the longer image side is resized to this length.")
    iou_threshold: Union[float, str] = Field(default=0.45, description="IoU threshold used by non-maximum suppression when merging overlapping boxes.")
    tracker: Union[Literal[ "bytetrack", "botsort" ], str] = Field(default="bytetrack", description="Underlying Ultralytics tracker used for association.")

class YoloFaceTrackingModelActionConfig(CommonFaceTrackingModelActionConfig):
    params: YoloFaceTrackingParamsConfig = Field(default_factory=YoloFaceTrackingParamsConfig, description="YOLO-specific face tracking parameters.")

    @model_validator(mode="after")
    def reject_embedding(self):
        # YOLO face models emit bounding boxes only; identity embeddings come
        # from a dedicated face-embedding model (InsightFace/FaceNet/Dlib).
        # Association here is spatial/motion-based via Ultralytics' tracker,
        # so `return_embedding` would silently return nothing — reject it
        # up front instead.
        if self.return_embedding is True:
            raise ValueError("'return_embedding' is not supported by the YOLO face tracker; identity embeddings require a face-embedding model.")
        return self
