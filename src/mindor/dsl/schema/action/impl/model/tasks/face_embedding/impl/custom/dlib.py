from pydantic import Field
from ..common import CommonFaceEmbeddingModelActionConfig, CommonFaceEmbeddingParamsConfig

class DlibFaceEmbeddingParamsConfig(CommonFaceEmbeddingParamsConfig):
    upsampling: int = Field(default=1, description="Number of times the image is upsampled before face detection.")
    detection_threshold: float = Field(default=0.0, description="Minimum detection confidence a face must reach.")
    num_jitters: int = Field(default=1, description="Number of times each face is re-sampled during encoding; higher values are more accurate but slower.")
    landmark_type: str = Field(default="68_point", description="Facial landmark model to use (e.g., 5_point, 68_point).")

class DlibFaceEmbeddingModelActionConfig(CommonFaceEmbeddingModelActionConfig):
    landmark_predictor_path: str = Field(default="shape_predictor_68_face_landmarks.dat", description="Path to the dlib facial landmark predictor model file.")
    recognition_model_path: str = Field(default="dlib_face_recognition_resnet_model_v1.dat", description="Path to the dlib face recognition model file.")
    params: DlibFaceEmbeddingParamsConfig = Field(default_factory=DlibFaceEmbeddingParamsConfig, description="dlib-specific face embedding parameters.")
