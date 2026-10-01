from typing import Union, Annotated
from pydantic import Field
from .rapidocr import RapidOcrImageToTextModelComponentConfig

CustomImageToTextModelComponentConfig = Annotated[
    Union[
        RapidOcrImageToTextModelComponentConfig,
    ],
    Field(discriminator="family")
]
