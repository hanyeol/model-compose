from typing import Union, Optional
from pydantic import Field
from ..common import CommonMusicTranscriptionModelActionConfig, CommonMusicTranscriptionParamsConfig

class GameMusicTranscriptionParamsConfig(CommonMusicTranscriptionParamsConfig):
    seg_threshold: Optional[Union[float, str]] = Field(default=None, description="Boundary decoding confidence threshold, from 0.0 to 1.0.")
    seg_radius: Optional[Union[int, str]] = Field(default=None, description="Boundary decoding radius in frames; a frame is kept when it is a local maximum within this window.")
    est_threshold: Optional[Union[float, str]] = Field(default=None, description="Note presence threshold, from 0.0 to 1.0; notes with lower confidence are marked unvoiced.")
    d3pm_steps: Optional[Union[int, str]] = Field(default=None, description="Number of D3PM sampling steps; ignored by models that don't support the sampling loop.")

class GameMusicTranscriptionModelActionConfig(CommonMusicTranscriptionModelActionConfig):
    language: Optional[Union[str]] = Field(default=None, description="Language of the vocal (e.g., 'en', 'ja', 'zh'); omit for the model's universal setting.")
    params: GameMusicTranscriptionParamsConfig = Field(default_factory=GameMusicTranscriptionParamsConfig, description="GAME boundary and pitch detection thresholds.")
