from enum import Enum

class TextToVideoModelFamily(str, Enum):
    WAN         = "wan"
    MINIMAX_H3  = "minimax-h3"
    PI_H3       = "pi-h3"
