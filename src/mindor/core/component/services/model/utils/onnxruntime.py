from __future__ import annotations

from typing import List, Optional, Tuple, Union, Dict, Any
from mindor.core.logger import logging
from .device import DeviceSpec

# Hardware-accelerated providers in the order we'd like them tried when the
# caller lets us pick (`device_type=None`). Ordered by expected throughput on
# the hardware they target: vendor-native kernels (TensorRT > CUDA on NVIDIA,
# ROCm on AMD, CoreML on Apple) come before cross-vendor fallbacks (DirectML
# on Windows, OpenVINO on Intel). In practice `ort.get_available_providers()`
# only lists what the installed wheel ships with, so at most one or two of
# these are real candidates on any given host. CPU is appended separately as
# the last-resort fallback.
_ACCELERATED_PROVIDERS = [
    "TensorrtExecutionProvider",
    "CUDAExecutionProvider",
    "ROCMExecutionProvider",
    "CoreMLExecutionProvider",
    "DmlExecutionProvider",
    "OpenVINOExecutionProvider",
]

# Map device types to the single onnxruntime execution provider that runs ops
# on that device. The `cuda`/`rocm`/`mps` keys line up with torch device types;
# `tensorrt`/`dml`/`openvino` are ONNX-only aliases that the torch resolver
# will refuse (surfaced as a clear error at `_resolve_device(use_torch=True)`).
# None (auto-select) is handled specially.
_DEVICE_TYPE_PROVIDER_MAP = {
    "cpu":      "CPUExecutionProvider",
    "cuda":     "CUDAExecutionProvider",
    "rocm":     "ROCMExecutionProvider",
    "mps":      "CoreMLExecutionProvider",
    "tensorrt": "TensorrtExecutionProvider",
    "dml":      "DmlExecutionProvider",
    "openvino": "OpenVINOExecutionProvider",
}

# Providers that accept a numeric `device_id` option. CoreML, OpenVINO and
# plain CPU don't — CoreML targets the single Apple Neural Engine / integrated
# GPU, OpenVINO uses a `device_type` string ("CPU"/"GPU"/"NPU") instead, and
# CPU EP has no device concept. Passing a device_id to these is silently
# ignored (not a warning) so `device: mps` / `device: openvino` / `device: cpu`
# stay no-ops.
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
