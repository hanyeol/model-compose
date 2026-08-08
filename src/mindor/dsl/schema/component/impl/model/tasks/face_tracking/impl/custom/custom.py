from typing import Union, Annotated
from pydantic import Field
from .impl.insightface import InsightfaceFaceTrackingModelComponentConfig

CustomFaceTrackingModelComponentConfig = Annotated[
    Union[
        InsightfaceFaceTrackingModelComponentConfig,
    ],
    Field(discriminator="family")
]
