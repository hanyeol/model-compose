from enum import Enum

class LipSyncModelFamily(str, Enum):
    WAV2LIP    = "wav2lip"
    LATENTSYNC = "latentsync"
    MUSETALK   = "musetalk"
