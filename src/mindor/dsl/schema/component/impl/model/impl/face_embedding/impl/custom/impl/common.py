from enum import Enum

class FaceEmbeddingModelFamily(str, Enum):
    INSIGHTFACE = "insightface"
    FACENET     = "facenet"
    DLIB        = "dlib"
