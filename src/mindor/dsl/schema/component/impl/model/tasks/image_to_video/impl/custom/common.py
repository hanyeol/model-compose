from enum import Enum

class ImageToVideoModelFamily(str, Enum):
    WAN = "wan"

class WanImageToVideoPreset(str, Enum):
    I2V_A14B = "i2v-a14b"
    TI2V_5B  = "ti2v-5b"
