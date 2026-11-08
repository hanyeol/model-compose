from typing import Union
from .birefnet import BiRefNetImageBackgroundRemovalModelActionConfig
from .ben2 import Ben2ImageBackgroundRemovalModelActionConfig

CustomImageBackgroundRemovalModelActionConfig = Union[
    BiRefNetImageBackgroundRemovalModelActionConfig,
    Ben2ImageBackgroundRemovalModelActionConfig,
]
