from __future__ import annotations
from typing import TYPE_CHECKING

from mindor.core.logger import logging

if TYPE_CHECKING:
    import torch

class DeviceResolver:
    def resolve(self, device: str) -> torch.device:
        import torch

        if device == "auto":
            if torch.cuda.is_available():
                return torch.device("cuda")

            if torch.backends.mps.is_available():
                return torch.device("mps")

            return torch.device("cpu")

        try:
            return torch.device(device)
        except:
            logging.warning(f"Invalid device '{device}', falling back to 'cpu'")

        return torch.device("cpu")
