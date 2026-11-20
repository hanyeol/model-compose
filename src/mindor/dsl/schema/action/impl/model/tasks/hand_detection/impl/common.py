from typing import Literal, Optional, Union, List
from pydantic import BaseModel, Field
from mindor.dsl.schema.common.color import Color
from ...common import CommonModelActionConfig

class CommonHandDetectionParamsConfig(BaseModel):
    min_confidence: Union[float, str] = Field(default=0.5, description="Minimum confidence the palm detector must reach for a hand to be returned.")
    min_presence_confidence: Union[float, str] = Field(default=0.5, description="Minimum presence confidence a keypoint must reach.")
    min_tracking_confidence: Union[float, str] = Field(default=0.5, description="Minimum tracking confidence in video mode.")

class CommonHandDetectionModelActionConfig(CommonModelActionConfig):
    image: Union[str, List[str]] = Field(..., description="Input image or list of images to detect hands in.")
    max_detection_count: Union[int, str] = Field(default=2, description="Maximum number of hands returned per image.")
    skeleton_format: Union[Literal[ "natural", "openpose" ], str] = Field(default="natural", description="Layout used when rendering the skeleton image.")
    crop_margin_ratio: Union[float, str] = Field(default=0.0, description="Margin added around each returned bounding box, as a ratio of the box's own width/height.")
    return_keypoints: Union[bool, str] = Field(default=True, description="Whether 2D keypoints (21 per hand) are included in the result.")
    return_keypoints_3d: Union[bool, str] = Field(default=False, description="Whether 3D world keypoints (meters, wrist-centered) are included in the result.")
    return_segmentation_mask: Union[bool, str] = Field(default=False, description="Whether a per-hand grayscale mask (convex hull of the 21 keypoints) is included in the result.")
    return_skeleton_image: Union[bool, str] = Field(default=False, description="Whether a rendered per-hand skeleton image is included in the result.")
    skeleton_background: Optional[Union[Color, str]] = Field(default=None, description="Skeleton canvas background: None yields a transparent RGBA PNG; a color (e.g. '#000000') flattens to that solid RGB fill.")
    batch_size: Union[int, str] = Field(default=1, description="Number of input images processed per batch.")
    params: CommonHandDetectionParamsConfig = Field(default_factory=CommonHandDetectionParamsConfig, description="Detection confidence thresholds applied to the hand detector.")
