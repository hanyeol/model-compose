from typing import Union, Annotated
from pydantic import Field
from .hsemotion import HSEmotionFaceEmotionClassificationModelComponentConfig

CustomFaceEmotionClassificationModelComponentConfig = Annotated[
    Union[
        HSEmotionFaceEmotionClassificationModelComponentConfig,
    ],
    Field(discriminator="family")
]
