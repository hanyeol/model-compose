from pydantic import model_validator
from ...common import CommonPoseDetectionModelActionConfig

class YoloPoseDetectionModelActionConfig(CommonPoseDetectionModelActionConfig):
    @model_validator(mode="after")
    def validate_returns(self):
        if self.return_keypoints_3d is True:
            raise ValueError("'return_keypoints_3d' is not supported by the 'yolo' family")
        if self.return_segmentation_mask is True:
            raise ValueError("'return_segmentation_mask' is not supported by the 'yolo' family")
        return self
