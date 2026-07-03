from enum import Enum

class ImageUpscaleModelFamily(str, Enum):
    ESRGAN      = "esrgan"
    REAL_ESRGAN = "real-esrgan"
    LDSR        = "ldsr"
    SWINIR      = "swinir"
