from typing import Union, Annotated
from pydantic import Field
from .impl import *

MusicGenerationModelActionConfig = Annotated[
    Union[
        AceStepMusicGenerationModelGenerateActionConfig,
        AceStepMusicGenerationModelCoverActionConfig,
        AceStepMusicGenerationModelRewriteActionConfig,
        AceStepMusicGenerationModelExtendActionConfig,
        AceStepMusicGenerationModelLayerActionConfig,
        AceStepMusicGenerationModelAccompanyActionConfig,
    ],
    Field(discriminator="method")
]
