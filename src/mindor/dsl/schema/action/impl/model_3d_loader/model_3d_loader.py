from typing import Union
from .impl import *

Model3DLoaderActionConfig = Union[
    NativeModel3DLoaderActionConfig,
    BlenderModel3DLoaderActionConfig,
]
