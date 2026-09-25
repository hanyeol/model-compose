from typing import Literal, Optional, List
from enum import Enum
from pydantic import Field
from mindor.dsl.schema.action import ColmapCameraPoseEstimatorActionConfig
from .common import CommonCameraPoseEstimatorComponentConfig, CameraPoseEstimatorDriverType

class ColmapCameraModel(str, Enum):
    SIMPLE_PINHOLE         = "simple-pinhole"
    PINHOLE                = "pinhole"
    SIMPLE_RADIAL          = "simple-radial"
    RADIAL                 = "radial"
    OPENCV                 = "opencv"
    OPENCV_FISHEYE         = "opencv-fisheye"
    FULL_OPENCV            = "full-opencv"
    FOV                    = "fov"
    SIMPLE_RADIAL_FISHEYE  = "simple-radial-fisheye"
    RADIAL_FISHEYE         = "radial-fisheye"
    THIN_PRISM_FISHEYE     = "thin-prism-fisheye"

class ColmapMatcherType(str, Enum):
    EXHAUSTIVE = "exhaustive"
    SEQUENTIAL = "sequential"
    SPATIAL    = "spatial"
    VOCAB_TREE = "vocab-tree"

class ColmapCameraPoseEstimatorComponentConfig(CommonCameraPoseEstimatorComponentConfig):
    driver: Literal[CameraPoseEstimatorDriverType.COLMAP]
    camera_model: ColmapCameraModel = Field(default=ColmapCameraModel.OPENCV, description="COLMAP camera model assumed for input images.")
    single_camera: bool = Field(default=True, description="Whether all input images are assumed to share one camera and intrinsics.")
    matcher: ColmapMatcherType = Field(default=ColmapMatcherType.EXHAUSTIVE, description="Feature matching strategy applied across images.")
    use_gpu: bool = Field(default=False, description="Whether SIFT feature extraction runs on the GPU.")
    num_threads: Optional[int] = Field(default=None, description="Number of CPU threads used by COLMAP; auto when omitted.")
    actions: List[ColmapCameraPoseEstimatorActionConfig] = Field(default_factory=list)
