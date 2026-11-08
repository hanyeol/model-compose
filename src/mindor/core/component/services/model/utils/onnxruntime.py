from __future__ import annotations

from typing import List, Optional, Tuple, Union, Dict, Any
from mindor.core.logger import logging
from .device import DeviceSpec

# Hardware-accelerated providers in the order we'd like them tried when the
# caller lets us pick (`device_type=None`). CPU is appended separately as
# the last-resort fallback.
_ACCELERATED_PROVIDERS = [
    "CUDAExecutionProvider",
    "TensorrtExecutionProvider",
    "ROCMExecutionProvider",
    "CoreMLExecutionProvider",
    "DmlExecutionProvider",
]

# Map torch-style device types to the single onnxruntime execution provider
# that runs ops on that device. None (auto-select) is handled specially.
_DEVICE_TYPE_PROVIDER_MAP = {
    "cpu":  "CPUExecutionProvider",
    "cuda": "CUDAExecutionProvider",
    "rocm": "ROCMExecutionProvider",
    "mps":  "CoreMLExecutionProvider",
}

# Providers that accept a numeric `device_id` option. CoreML and plain CPU
# don't — CoreML targets the single Apple Neural Engine / integrated GPU,
# and CPU EP has no device concept. Passing a device_id to these is silently
# ignored (not a warning) so `device: mps` and `device: cpu` stay no-ops.
_DEVICE_ID_CAPABLE_PROVIDERS = {
    "CUDAExecutionProvider",
    "ROCMExecutionProvider",
    "DmlExecutionProvider",
    "TensorrtExecutionProvider",
}

ProviderSpec = Union[str, Tuple[str, Dict[str, Any]]]

def resolve_onnx_providers(device: Optional[DeviceSpec]) -> List[ProviderSpec]:
    """Pick an onnxruntime provider list for `device` (None or DeviceSpec(None,...) = auto), always ending in CPU as fallback."""
    import onnxruntime as ort

    available = set(ort.get_available_providers())
    cpu_provider = _DEVICE_TYPE_PROVIDER_MAP["cpu"]

    if device is not None and device.type is not None:
        provider = _DEVICE_TYPE_PROVIDER_MAP.get(device.type)

        if provider is None:
            logging.warning(f"Unknown onnxruntime device type '{device.type}', falling back to CPU")

            return [ cpu_provider ]

        if provider == cpu_provider:
            return [ cpu_provider ]

        if provider not in available:
            logging.warning(
                f"Requested onnxruntime provider '{provider}' for device '{device.type}' is not "
                f"available; falling back to CPU"
            )

            return [ cpu_provider ]

        if device.index is not None and provider in _DEVICE_ID_CAPABLE_PROVIDERS:
            return [ (provider, { "device_id": device.index }), cpu_provider ]

        return [ provider, cpu_provider ]

    return [ provider for provider in _ACCELERATED_PROVIDERS if provider in available ] + [ cpu_provider ]
