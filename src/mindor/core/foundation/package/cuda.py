from typing import Optional, Tuple
import functools, platform, re, shutil, subprocess, sys

def is_cuda_installed() -> bool:
    """True when `nvidia-smi` is on PATH (proxy for a usable NVIDIA driver)."""
    if sys.platform != "linux" or platform.machine() != "x86_64":
        return False

    return shutil.which("nvidia-smi") is not None

@functools.lru_cache(maxsize=1)
def get_cuda_driver_version() -> Optional[Tuple[int, int]]:
    """Detect the host NVIDIA driver's CUDA runtime version via `nvidia-smi`.

    Returns (major, minor) on Linux x86_64 when a working driver is present,
    None otherwise (non-Linux, non-x86_64, no nvidia-smi, or probe failure).
    """
    if sys.platform != "linux" or platform.machine() != "x86_64":
        return None

    return _probe_cuda_driver_version()

def _probe_cuda_driver_version() -> Optional[Tuple[int, int]]:
    nvidia_smi = shutil.which("nvidia-smi")

    if nvidia_smi is None:
        return None

    try:
        result = subprocess.run(
            [ nvidia_smi ],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (subprocess.SubprocessError, OSError):
        return None

    if result.returncode != 0:
        return None

    match = re.search(r"CUDA Version:\s*(\d+)\.(\d+)", result.stdout)

    if match is None:
        return None

    return int(match.group(1)), int(match.group(2))
