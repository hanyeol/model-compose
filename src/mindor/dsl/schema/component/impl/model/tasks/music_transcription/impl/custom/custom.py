from typing import Union, Annotated
from pydantic import Field
from .basic_pitch import BasicPitchMusicTranscriptionModelComponentConfig
from .piano_transcription import PianoTranscriptionMusicTranscriptionModelComponentConfig
from .game import GameMusicTranscriptionModelComponentConfig

CustomMusicTranscriptionModelComponentConfig = Annotated[
    Union[
        BasicPitchMusicTranscriptionModelComponentConfig,
        PianoTranscriptionMusicTranscriptionModelComponentConfig,
        GameMusicTranscriptionModelComponentConfig,
    ],
    Field(discriminator="family")
]
