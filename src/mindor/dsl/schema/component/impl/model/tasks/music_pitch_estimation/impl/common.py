from typing import Literal
from ...common import CommonModelComponentConfig, ModelTaskType

class CommonMusicPitchEstimationModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.MUSIC_PITCH_ESTIMATION]
