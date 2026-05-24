from pydantic import Field
from ..common import CommonFaceEmbeddingModelActionConfig

class DlibFaceEmbeddingModelActionConfig(CommonFaceEmbeddingModelActionConfig):
    # Model paths
    landmark_predictor_path: str = Field(default="shape_predictor_68_face_landmarks.dat", description="Path to dlib facial landmark predictor model.")
    recognition_model_path: str = Field(default="dlib_face_recognition_resnet_model_v1.dat", description="Path to dlib face recognition model.")

    # Detection settings
    upsampling: int = Field(default=1, description="Number of times to upsample the image for face detection.")
    detection_threshold: float = Field(default=0.0, description="Detection confidence threshold.")

    # Landmark settings
    num_jitters: int = Field(default=1, description="Number of times to re-sample face for encoding (higher = more accurate but slower).")
    landmark_type: str = Field(default="68_point", description="Facial landmark model type (5_point, 68_point).")
