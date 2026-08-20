from enum import Enum

class ImageToVideoModelFamily(str, Enum):
    WAN = "wan"

class WanImageToVideoPreset(str, Enum):
    WAN22_I2V_A14B = "wan2.2-i2v-a14b"
    WAN22_TI2V_5B  = "wan2.2-ti2v-5b"
