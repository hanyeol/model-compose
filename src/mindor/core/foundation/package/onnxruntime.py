from typing import List

# All of these distributions install the same `onnxruntime/` Python module,
# so pip will happily install one on top of another and overwrite the
# native binaries (CUDA/CoreML/DirectML/OpenVINO execution providers) that
# the earlier distribution shipped. Any component that declares
# `onnxruntime` should pass this list as `canonical_names` to
# `is_requirement_satisfied` so a user-installed accelerated build is
# recognized as satisfying the requirement and not clobbered by the CPU
# wheel at setup.
_ONNXRUNTIME_DISTRIBUTIONS: List[str] = [
    "onnxruntime",
    "onnxruntime-gpu",
    "onnxruntime-silicon",
    "onnxruntime-openvino",
    "onnxruntime-directml",
    "onnxruntime-training",
]

def get_onnxruntime_distributions() -> List[str]:
    return list(_ONNXRUNTIME_DISTRIBUTIONS)
