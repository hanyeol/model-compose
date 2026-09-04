from typing import Union, Annotated
from pydantic import Field
from .basic_pitch import BasicPitchMusicTranscriptionModelComponentConfig
from .piano_transcription import PianoTranscriptionMusicTranscriptionModelComponentConfig

CustomMusicTranscriptionModelComponentConfig = Annotated[
    Union[
        BasicPitchMusicTranscriptionModelComponentConfig,
        PianoTranscriptionMusicTranscriptionModelComponentConfig,
    ],
    Field(discriminator="family")
]
