from __future__ import annotations
from typing import TYPE_CHECKING

from typing import TypeGuard
import sys

if TYPE_CHECKING:
    import numpy as np

def is_numpy_array(value) -> TypeGuard[np.ndarray]:
    np = sys.modules.get("numpy")
    
    if np is not None:
        return isinstance(value, np.ndarray)

    return False
