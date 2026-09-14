from typing import Union, Optional
from enum import Enum
from pydantic import Field
from ..common import CommonLipSyncParamsConfig, CommonLipSyncModelActionConfig

class MuseTalkParsingMode(str, Enum):
    JAW  = "jaw"
    NECK = "neck"
    RAW  = "raw"

class MuseTalkLipSyncParamsConfig(CommonLipSyncParamsConfig):
    bbox_shift: Union[int, str] = Field(default=0, description="Vertical shift (in pixels) applied to the detected face bounding box; ignored on the v15 preset.")
    extra_margin: Union[int, str] = Field(default=10, description="Extra chin margin added to the face region before blending; v15 only.")
    parsing_mode: Union[MuseTalkParsingMode, str] = Field(default=MuseTalkParsingMode.JAW, description="Face parsing region used for blending; v15 only.")
    left_cheek_width: Union[int, str] = Field(default=90, description="Left cheek width in pixels used by the parsing mask; v15 only.")
    right_cheek_width: Union[int, str] = Field(default=90, description="Right cheek width in pixels used by the parsing mask; v15 only.")
    audio_padding_length_left: Union[int, str] = Field(default=2, description="Number of audio feature frames padded before each window.")
    audio_padding_length_right: Union[int, str] = Field(default=2, description="Number of audio feature frames padded after each window.")
    generator_batch_size: Union[int, str] = Field(default=8, description="Number of samples processed per MuseTalk generator batch.")
    use_float16: Union[bool, str] = Field(default=False, description="Whether to run the generator in float16 for a memory and latency win.")

class MuseTalkLipSyncModelActionConfig(CommonLipSyncModelActionConfig):
    params: MuseTalkLipSyncParamsConfig = Field(default_factory=MuseTalkLipSyncParamsConfig, description="MuseTalk generation parameters.")
