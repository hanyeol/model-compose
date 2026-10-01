from enum import Enum

class ImageUpscalingModelFamily(str, Enum):
    ESRGAN      = "esrgan"
    REAL_ESRGAN = "real-esrgan"
    LDSR        = "ldsr"
    SWINIR      = "swinir"
