from enum import Enum

class TextToVideoModelFamily(str, Enum):
    WAN = "wan"

class WanTextToVideoPreset(str, Enum):
    WAN22_T2V_A14B = "wan2.2-t2v-a14b"
    WAN22_TI2V_5B  = "wan2.2-ti2v-5b"
