from typing import Union, Annotated
from pydantic import Field
from .impl.insightface import InsightfaceFaceSwapModelComponentConfig

CustomFaceSwapModelComponentConfig = Annotated[
    Union[
        InsightfaceFaceSwapModelComponentConfig,
    ],
    Field(discriminator="family")
]
