from typing import Union, Annotated
from pydantic import Field
from .common import (
    BrightnessImageAnalyzerActionConfig,
    ContrastImageAnalyzerActionConfig,
    SharpnessImageAnalyzerActionConfig,
    ExposureImageAnalyzerActionConfig,
)

NativeImageAnalyzerActionConfig = Annotated[
    Union[
        BrightnessImageAnalyzerActionConfig,
        ContrastImageAnalyzerActionConfig,
        SharpnessImageAnalyzerActionConfig,
        ExposureImageAnalyzerActionConfig,
    ],
    Field(discriminator="metric")
]
