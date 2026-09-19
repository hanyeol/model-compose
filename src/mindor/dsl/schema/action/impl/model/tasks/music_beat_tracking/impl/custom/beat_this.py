from pydantic import Field
from ..common import CommonMusicBeatTrackingModelActionConfig, CommonMusicBeatTrackingParamsConfig

class BeatThisMusicBeatTrackingParamsConfig(CommonMusicBeatTrackingParamsConfig):
    pass

class BeatThisMusicBeatTrackingModelActionConfig(CommonMusicBeatTrackingModelActionConfig):
    params: BeatThisMusicBeatTrackingParamsConfig = Field(default_factory=BeatThisMusicBeatTrackingParamsConfig, description="Beat This! beat tracking parameters.")
