from typing import Union
from .impl import *

DocumentLoaderActionConfig = Union[
    DoclingDocumentLoaderActionConfig,
    PypdfDocumentLoaderActionConfig,
]
