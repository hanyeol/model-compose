from typing import Tuple
from pydantic import Field
from ...common import CommonFaceEmbeddingModelActionConfig, CommonFaceEmbeddingParamsConfig

class FacenetFaceEmbeddingParamsConfig(CommonFaceEmbeddingParamsConfig):
    crop_margin: float = Field(default=44.0, description="Margin in pixels added around each face crop.")
    image_size: int = Field(default=160, description="Square input image size in pixels used by FaceNet.")
    prewhiten: bool = Field(default=True, description="Whether input images are prewhitened before embedding.")
    detection_threshold: Tuple[float, float, float] = Field(default=(0.6, 0.7, 0.7), description="MTCNN detection thresholds for P-Net, R-Net, and O-Net.")
    scale_factor: float = Field(default=0.709, description="Scale factor used by MTCNN when building the image pyramid.")

class FacenetFaceEmbeddingModelActionConfig(CommonFaceEmbeddingModelActionConfig):
    params: FacenetFaceEmbeddingParamsConfig = Field(default_factory=FacenetFaceEmbeddingParamsConfig, description="FaceNet-specific face embedding parameters.")
