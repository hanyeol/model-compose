from typing import Optional, List, Tuple, Dict, Iterable
from packaging.requirements import Requirement
from packaging.version import Version
from packaging.specifiers import SpecifierSet
from mindor.core.logger import logging
from .cuda import is_cuda_installed
import sys, platform

# flash-attn ships pre-built wheels only via GitHub releases (pypi has just the
# sdist, which triggers a slow nvcc build). Each wheel encodes the (torch
# major.minor, CUDA major, cxx11abi, python minor, arch) tuple it was built
# against — the runtime torch install must match exactly.
#
# This module targets a single release tag (v2.8.3.post1) which covers torch
# 2.4–2.9 on Linux x86_64. Combos outside the matrix return the spec unchanged
# so pip can attempt its own resolution (usually the slow source build; callers
# who cannot afford that fallback should filter the result and drop the spec).

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

# torch minor → python minors that have a pre-built wheel.
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

    Reads the intended torch version from the same `specs` iterable (i.e. the
    caller passes both the `torch` spec and the `flash-attn` spec together),
    so the wheel URL matches the torch build that will be installed alongside
    it. Callers usually chain this after `torch_requirements(...)` and hand
    the concatenated list to the installer.

    Returns specs unchanged when the host isn't Linux x86_64 with a working
    NVIDIA driver, or when the requested (torch minor, python minor) combo
    isn't in our wheel matrix. pip then falls back to its own resolution,
    which for flash-attn usually means an nvcc source build.
    """
    if sys.platform != "linux" or platform.machine() != "x86_64":
        return list(specs)

    if not is_cuda_installed():
        return list(specs)

    torch_specifier = _get_torch_specifier(specs)
    torch_minor = _resolve_torch_minor(torch_specifier)

    if torch_minor is None:
        return list(specs)

    py_minor = sys.version_info.minor

    if py_minor not in _SUPPORTED_PYTHON_MINORS.get(torch_minor, []):
        logging.warning(
            f"No pre-built flash-attn wheel for python 3.{py_minor} on torch {torch_minor}; "
            f"leaving the spec unresolved (pip will fall back to a source build)."
        )
        return list(specs)

    wheel_version, cuda_major, cxx11abi = _TORCH_MINOR_TO_WHEEL[torch_minor]
    rewritten_specs: List[str] = []

    for spec in specs:
        requirement = _parse_requirement(spec)

        if requirement is None or requirement.name != _FLASH_ATTN_PACKAGE_NAME:
            rewritten_specs.append(spec)
            continue

        if requirement.url is not None:
            rewritten_specs.append(spec)
            continue

        wheel_url = (
            f"{_RELEASE_BASE}/"
            f"flash_attn-{wheel_version}+cu{cuda_major}torch{torch_minor}cxx11abi{cxx11abi}"
            f"-cp3{py_minor}-cp3{py_minor}-linux_x86_64.whl"
        )
        rewritten_specs.append(f"{spec}@{wheel_url}")

    return rewritten_specs

def _get_torch_specifier(specs: Iterable[str]) -> Optional[SpecifierSet]:
    for spec in specs:
        requirement = _parse_requirement(spec)

        if requirement is not None and requirement.name == "torch":
            return requirement.specifier if str(requirement.specifier) else None

    return None

def _resolve_torch_minor(torch_specifier: Optional[SpecifierSet]) -> Optional[str]:
    """Pick the highest torch minor in our matrix that satisfies the specifier."""
    candidates = sorted(_TORCH_MINOR_TO_WHEEL.keys(), key=Version, reverse=True)

    if torch_specifier is None:
        return candidates[0] if candidates else None

    for minor in candidates:
        # A minor like "2.8" satisfies the specifier if any of its patch releases
        # would; test with the ".0" representative — good enough since our matrix
        # keys are minor-granular.
        if torch_specifier.contains(f"{minor}.0", prereleases=True):
            return minor

    return None

def _parse_requirement(spec: str) -> Optional[Requirement]:
    try:
        return Requirement(spec)
    except Exception:
        return None
