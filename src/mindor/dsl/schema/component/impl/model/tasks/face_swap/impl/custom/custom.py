from typing import Union, Annotated
from pydantic import Field
from .insightface import InsightfaceFaceSwapModelComponentConfig

CustomFaceSwapModelComponentConfig = Annotated[
    Union[
        InsightfaceFaceSwapModelComponentConfig,
    ],
    Field(discriminator="family")
]
