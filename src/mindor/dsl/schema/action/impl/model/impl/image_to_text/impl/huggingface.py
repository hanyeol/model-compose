from enum import Enum

class HuggingfaceImageToTextModelArchitecture(str, Enum):
    BLIP       = "blip"
    BLIP2      = "blip2"
    GIT        = "git"
    PIX2STRUCT = "pix2struct"
    DONUT      = "donut"
    KOSMOS2    = "kosmos2"
