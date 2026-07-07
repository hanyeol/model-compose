from typing import Union, Annotated
from pydantic import Field
from .impl import *

AudioFeatureExtractorActionConfig = Annotated[
    Union[
        SpectrumAudioFeatureExtractorActionConfig,
        WaveformAudioFeatureExtractorActionConfig,
    ],
    Field(discriminator="feature")
]
