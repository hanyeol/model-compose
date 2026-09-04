from typing import Union, Annotated
from pydantic import Field
from .insightface import InsightfaceFaceTrackingModelComponentConfig

CustomFaceTrackingModelComponentConfig = Annotated[
    Union[
        InsightfaceFaceTrackingModelComponentConfig,
    ],
    Field(discriminator="family")
]
