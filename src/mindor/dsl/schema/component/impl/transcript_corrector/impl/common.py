from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class TranscriptCorrectorDriver(str, Enum):
    NATIVE = "native"

class CommonTranscriptCorrectorComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.TRANSCRIPT_CORRECTOR]
    driver: TranscriptCorrectorDriver = Field(..., description="Backend implementation used to correct transcripts.")
