from typing import Union, Annotated
from pydantic import Field
from .impl.basic_pitch import BasicPitchMusicTranscriptionModelComponentConfig
from .impl.piano_transcription import PianoTranscriptionMusicTranscriptionModelComponentConfig

CustomMusicTranscriptionModelComponentConfig = Annotated[
    Union[
        BasicPitchMusicTranscriptionModelComponentConfig,
        PianoTranscriptionMusicTranscriptionModelComponentConfig,
    ],
    Field(discriminator="family")
]
