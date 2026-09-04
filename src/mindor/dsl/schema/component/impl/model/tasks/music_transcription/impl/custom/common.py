from enum import Enum

class MusicTranscriptionModelFamily(str, Enum):
    BASIC_PITCH         = "basic-pitch"
    PIANO_TRANSCRIPTION = "piano-transcription"
