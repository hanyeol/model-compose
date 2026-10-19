from __future__ import annotations

from typing import List

def resolve_onnx_providers() -> List[str]:
    """Prefer hardware-accelerated onnxruntime providers over CPU. onnxruntime's
    default provider list is `[CUDA, CPU]`, so on Apple Silicon it silently falls
    back to CPU and per-frame inference can take seconds. Adding CoreML (Apple),
    then any available GPU providers ahead of CPU restores hardware acceleration."""
    import onnxruntime as ort

    available = set(ort.get_available_providers())
    preferred = [
        "CUDAExecutionProvider",
        "TensorrtExecutionProvider",
        "ROCMExecutionProvider",
        "CoreMLExecutionProvider",
        "DmlExecutionProvider",
    ]

    providers = [ provider for provider in preferred if provider in available ]
    providers.append("CPUExecutionProvider")

    return providers
