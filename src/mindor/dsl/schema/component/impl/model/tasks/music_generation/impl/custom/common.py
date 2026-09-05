from enum import Enum

class MusicGenerationModelFamily(str, Enum):
    ACE_STEP  = "ace-step"
    MIDI_DDSP = "midi-ddsp"
