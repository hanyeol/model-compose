from typing import Union, Annotated
from pydantic import Field
from .hed import HedImageEdgeDetectionModelComponentConfig
from .pidinet import PidinetImageEdgeDetectionModelComponentConfig
from .lineart import LineartImageEdgeDetectionModelComponentConfig

CustomImageEdgeDetectionModelComponentConfig = Annotated[
    Union[
        HedImageEdgeDetectionModelComponentConfig,
        PidinetImageEdgeDetectionModelComponentConfig,
        LineartImageEdgeDetectionModelComponentConfig,
    ],
    Field(discriminator="family")
]
