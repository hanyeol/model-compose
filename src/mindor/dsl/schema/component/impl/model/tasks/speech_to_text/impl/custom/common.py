from enum import Enum

class SpeechToTextModelFamily(str, Enum):
    FASTER_WHISPER  = "faster-whisper"
    FUN_ASR         = "fun-asr"
    CRISPER_WHISPER = "crisper-whisper"
    VIBEVOICE       = "vibevoice"
