from typing import Tuple
from pydantic import Field
from ...common import CommonFaceEmbeddingModelActionConfig, CommonFaceEmbeddingParamsConfig

class FacenetFaceEmbeddingParamsConfig(CommonFaceEmbeddingParamsConfig):
    crop_margin: float = Field(default=44.0, description="Margin for face cropping.")
    image_size: int = Field(default=160, description="Input image size for FaceNet (square).")
    prewhiten: bool = Field(default=True, description="Whether to prewhiten input images.")
    detection_threshold: Tuple[float, float, float] = Field(default=(0.6, 0.7, 0.7), description="MTCNN detection thresholds for P-Net, R-Net, and O-Net.")
    scale_factor: float = Field(default=0.709, description="Scale factor for MTCNN.")

class FacenetFaceEmbeddingModelActionConfig(CommonFaceEmbeddingModelActionConfig):
    params: FacenetFaceEmbeddingParamsConfig = Field(default_factory=FacenetFaceEmbeddingParamsConfig, description="Face embedding parameters.")
