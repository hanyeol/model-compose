from enum import Enum

class ImageEdgeDetectionModelFamily(str, Enum):
    HED     = "hed"
    PIDINET = "pidinet"
    LINEART = "lineart"

class LineartVariant(str, Enum):
    REALISTIC = "realistic"
    COARSE    = "coarse"
