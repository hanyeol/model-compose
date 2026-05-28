from typing import Union, Annotated
from pydantic import Field
from .impl.sdxl import SdxlImageGenerationModelComponentConfig
from .impl.flux import FluxImageGenerationModelComponentConfig
from .impl.hunyuan_image import HunyuanImageGenerationModelComponentConfig

CustomImageGenerationModelComponentConfig = Annotated[
    Union[
        SdxlImageGenerationModelComponentConfig,
        FluxImageGenerationModelComponentConfig,
        HunyuanImageGenerationModelComponentConfig,
    ],
    Field(discriminator="family")
]
