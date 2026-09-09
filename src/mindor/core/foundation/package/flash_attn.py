from typing import Optional, List, Tuple, Dict
from packaging.requirements import Requirement
from packaging.version import Version
from mindor.core.logger import logging
from .cuda import is_cuda_installed
import sys, platform, importlib.metadata

# flash-attn ships pre-built wheels only via GitHub releases (pypi has just the
# sdist, which triggers a slow nvcc build). Each wheel encodes the (torch major.minor,
# CUDA major, cxx11abi, python minor, arch) tuple it was built against — the
# runtime torch install must match exactly.
#
# This module targets a single release tag (v2.8.3.post1) which covers torch 2.4–2.9
# on Linux x86_64. Combos outside the matrix return the spec unchanged so pip
# can attempt its own resolution (usually the slow source build; callers may
# choose to drop flash-attn instead).

_RELEASE_TAG = "v2.8.3.post1"
_RELEASE_BASE = f"https://github.com/Dao-AILab/flash-attention/releases/download/{_RELEASE_TAG}"

# torch minor → (wheel version tag, cuda major, cxx11abi flag)
# `wheel version tag` differs from the release tag: the 2.9-targeted wheels are
# tagged 2.8.3, the rest are 2.8.3.post1.
_TORCH_MINOR_TO_WHEEL: Dict[str, Tuple[str, str, str]] = {
    "2.4": ("2.8.3.post1", "12", "FALSE"),
    "2.5": ("2.8.3.post1", "12", "FALSE"),
    "2.6": ("2.8.3.post1", "12", "FALSE"),
    "2.7": ("2.8.3.post1", "12", "FALSE"),
    "2.8": ("2.8.3.post1", "12", "FALSE"),
    "2.9": ("2.8.3",       "13", "TRUE"),
}

# python minor supported per (torch minor, cuda major) — torch 2.4 has no cp313 wheel;
# torch 2.9 has only cp312.
_SUPPORTED_PYTHON_MINORS: Dict[str, List[int]] = {
    "2.4": [9, 10, 11, 12],
    "2.5": [9, 10, 11, 12, 13],
    "2.6": [9, 10, 11, 12, 13],
    "2.7": [9, 10, 11, 12, 13],
    "2.8": [9, 10, 11, 12, 13],
    "2.9": [12],
}

_FLASH_ATTN_PACKAGE_NAME = "flash-attn"

def flash_attn_requirements(*specs: str) -> List[str]:
    """Attach a pre-built GitHub wheel URL to each flash-attn spec.

    Requires Linux x86_64, a working NVIDIA driver, and an already-installed
    torch whose (major.minor) is in our wheel matrix. Returns specs unchanged
    on unsupported hosts so pip falls back to its own resolution — which for
    flash-attn typically means an nvcc source build. Callers who cannot afford
    that fallback should filter the result and drop the spec.
    """
    if sys.platform != "linux" or platform.machine() != "x86_64":
        return list(specs)

    if not is_cuda_installed():
        return list(specs)

    torch_minor = _detect_installed_torch_minor()

    if torch_minor is None or torch_minor not in _TORCH_MINOR_TO_WHEEL:
        return list(specs)

    py_minor = sys.version_info.minor

    if py_minor not in _SUPPORTED_PYTHON_MINORS.get(torch_minor, []):
        logging.warning(
            f"No pre-built flash-attn wheel for python 3.{py_minor} on torch {torch_minor}; "
            f"leaving the spec unresolved (pip will fall back to a source build)."
        )
        return list(specs)

    wheel_version, cuda_major, cxx11abi = _TORCH_MINOR_TO_WHEEL[torch_minor]
    rewritten: List[str] = []

    for spec in specs:
        requirement = _parse_requirement(spec)

        if requirement is None or requirement.name != _FLASH_ATTN_PACKAGE_NAME:
            rewritten.append(spec)
            continue

        if requirement.url is not None:
            rewritten.append(spec)
            continue

        wheel_url = (
            f"{_RELEASE_BASE}/"
            f"flash_attn-{wheel_version}+cu{cuda_major}torch{torch_minor}cxx11abi{cxx11abi}"
            f"-cp3{py_minor}-cp3{py_minor}-linux_x86_64.whl"
        )
        rewritten.append(f"{spec}@{wheel_url}")

    return rewritten

def _detect_installed_torch_minor() -> Optional[str]:
    try:
        installed = importlib.metadata.version("torch")
    except importlib.metadata.PackageNotFoundError:
        return None

    version = Version(installed)
    return f"{version.major}.{version.minor}"

def _parse_requirement(spec: str) -> Optional[Requirement]:
    try:
        return Requirement(spec)
    except Exception:
        return None
