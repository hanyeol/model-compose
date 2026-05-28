from enum import Enum

class ImageGenerationModelFamily(str, Enum):
    SDXL          = "sdxl"
    FLUX          = "flux"
    HUNYUAN_IMAGE = "hunyuan-image"
