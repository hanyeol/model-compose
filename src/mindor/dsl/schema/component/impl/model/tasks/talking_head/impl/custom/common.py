from enum import Enum

class TalkingHeadModelFamily(str, Enum):
    SADTALKER = "sadtalker"
    HALLO2    = "hallo2"
    HALLO3    = "hallo3"
    SONIC     = "sonic"
    ECHOMIMIC = "echomimic"
    FLOAT     = "float"

class SadTalkerPreset(str, Enum):
    V002_256 = "v0.0.2-256"
    V002_512 = "v0.0.2-512"

class EchoMimicPreset(str, Enum):
    V1 = "v1"
    V2 = "v2"
