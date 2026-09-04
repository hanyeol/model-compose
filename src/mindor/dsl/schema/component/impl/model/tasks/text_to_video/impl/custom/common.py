from enum import Enum

class TextToVideoModelFamily(str, Enum):
    WAN = "wan"

class WanTextToVideoPreset(str, Enum):
    T2V_A14B = "t2v-a14b"
    TI2V_5B  = "ti2v-5b"
