from __future__ import annotations
from typing import TYPE_CHECKING

from typing import NamedTuple, Optional, Union
from mindor.core.logger import logging

if TYPE_CHECKING:
    import torch

class DeviceSpec(NamedTuple):
    type: Optional[str]
    index: Optional[int]

class DeviceResolver:
    def resolve(self, device: str, use_torch: bool = True) -> Union[torch.device, DeviceSpec]:
        if use_torch:
            return self._resolve_as_torch(device)

        return self._resolve_as_spec(device)

    @staticmethod
    def _resolve_as_torch(device: str) -> torch.device:
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

    @staticmethod
    def _resolve_as_spec(device: str) -> DeviceSpec:
        if device != "auto":
            parts = device.split(":", 1)

            if len(parts) == 2:
                return DeviceSpec(parts[0], int(parts[1]))

            return DeviceSpec(parts[0], None)

        return DeviceSpec(None, None)
