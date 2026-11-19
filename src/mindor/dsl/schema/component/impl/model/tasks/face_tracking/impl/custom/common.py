from enum import Enum

class FaceTrackingModelFamily(str, Enum):
    INSIGHTFACE = "insightface"
    YOLO        = "yolo"
