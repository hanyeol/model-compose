from enum import Enum

class MusicSourceSeparationModelFamily(str, Enum):
    DEMUCS            = "demucs"
    MDX_NET           = "mdx-net"
    BS_ROFORMER       = "bs-roformer"
    MEL_BAND_ROFORMER = "mel-band-roformer"
