from typing import Union
from .hed import HedImageEdgeDetectionModelActionConfig
from .pidinet import PidinetImageEdgeDetectionModelActionConfig
from .lineart import LineartImageEdgeDetectionModelActionConfig

CustomImageEdgeDetectionModelActionConfig = Union[
    HedImageEdgeDetectionModelActionConfig,
    PidinetImageEdgeDetectionModelActionConfig,
    LineartImageEdgeDetectionModelActionConfig,
]
