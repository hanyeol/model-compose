from enum import Enum

class MusicGenerationModelFamily(str, Enum):
    ACE_STEP        = "ace-step"
    MIDI_DDSP       = "midi-ddsp"
    YUE2            = "yue2"
    MINIMAX_MUSIC3  = "minimax-music3"
