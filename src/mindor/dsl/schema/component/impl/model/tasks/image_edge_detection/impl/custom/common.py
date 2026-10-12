from enum import Enum

class ImageEdgeDetectionModelFamily(str, Enum):
    HED     = "hed"
    PIDINET = "pidinet"
    LINEART = "lineart"
