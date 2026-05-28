from enum import Enum

class TextToSpeechModelFamily(str, Enum):
    QWEN       = "qwen"
    KOKORO     = "kokoro"
    CHATTERBOX = "chatterbox"
