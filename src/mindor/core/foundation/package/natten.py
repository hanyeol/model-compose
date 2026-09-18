from typing import Optional, List, Tuple, Dict
from packaging.requirements import Requirement
from packaging.version import Version
from packaging.specifiers import SpecifierSet
from mindor.core.logger import logging
from .cuda import get_cuda_driver_version
import sys, platform

# natten ships pre-built wheels only via GitHub releases (pypi has just the
# sdist, which triggers a slow nvcc build that also requires torch at
# `setup.py` import time — pip's default isolated build env doesn't provide
# torch, so the build wheel step aborts with `ModuleNotFoundError: No module
# named 'torch'` before it even sees the caller's environment). Each wheel
# encodes the (natten version, torch minor, CUDA major/minor, python minor,
# arch) tuple it was built against — the runtime torch install must match
# exactly.
#
# This module targets a single release tag (v0.21.0) which pairs with torch
# 2.7 on Linux x86_64. Combos outside the matrix return the spec unchanged so
# pip attempts its own resolution (the sdist source build described above;
# callers who cannot afford that fallback should filter the result and drop
# the spec).

_RELEASE_TAG = "v0.21.0"
_RELEASE_BASE = f"https://github.com/SHI-Labs/NATTEN/releases/download/{_RELEASE_TAG}"

_NATTEN_PACKAGE_NAME = "natten"

# natten version → (torch minor tag used in the wheel, CUDA channels the
# release provides, ordered high-to-low). Each CUDA channel pairs a wheel
# tag (`cu128`) with the minimum driver CUDA version it needs, matching the
# ordering rules used by `torch.py`.
_NATTEN_VERSION_MATRIX: Dict[str, Tuple[str, List[Tuple[Tuple[int, int], str]]]] = {
    "0.21.0": ("270", [((12, 8), "cu128"), ((12, 6), "cu126")]),
}

# python minors that have a pre-built wheel for each natten release.
_SUPPORTED_PYTHON_MINORS: Dict[str, List[int]] = {
    "0.21.0": [10, 11, 12, 13],
}

def natten_requirements(*specs: str) -> List[str]:
    """Attach a pre-built GitHub wheel URL to each natten spec.

    Reads the exact natten version from the caller's specifier (e.g.
    `"natten==0.21.0"`) and picks the CUDA channel that matches the host's
    NVIDIA driver. Returns specs unchanged when the host isn't Linux x86_64
    with a working NVIDIA driver, when the natten version isn't in our matrix,
    or when the running Python minor lacks a pre-built wheel — pip then falls
    back to its own resolution, which for natten means the sdist source build.
    """
    if sys.platform != "linux" or platform.machine() != "x86_64":
        return list(specs)

    cuda_version = get_cuda_driver_version()

    if cuda_version is None:
        return list(specs)

    rewritten_specs: List[str] = []

    for spec in specs:
        requirement = _parse_requirement(spec)

        if requirement is None or requirement.name != _NATTEN_PACKAGE_NAME or requirement.url is not None:
            rewritten_specs.append(spec)
            continue

        natten_version = _resolve_exact_version(requirement.specifier)

        if natten_version is None:
            rewritten_specs.append(spec)
            continue

        torch_tag, cuda_channels = _NATTEN_VERSION_MATRIX[natten_version]
        channel = _pick_cuda_channel(cuda_channels, cuda_version)

        if channel is None:
            logging.warning(
                f"No pre-built natten {natten_version} wheel for driver CUDA "
                f"{cuda_version[0]}.{cuda_version[1]}; leaving the spec "
                f"unresolved (pip will fall back to a source build)."
            )
            rewritten_specs.append(spec)
            continue

        py_minor = sys.version_info.minor

        if py_minor not in _SUPPORTED_PYTHON_MINORS.get(natten_version, []):
            logging.warning(
                f"No pre-built natten {natten_version} wheel for python 3.{py_minor}; "
                f"leaving the spec unresolved (pip will fall back to a source build)."
            )
            rewritten_specs.append(spec)
            continue

        # The `+` in the wheel version tag has to be percent-encoded for pip to
        # download the file directly (GitHub Release URLs treat `+` as literal,
        # but pip strips it when parsing the direct URL otherwise).
        wheel_url = (
            f"{_RELEASE_BASE}/"
            f"natten-{natten_version}%2Btorch{torch_tag}{channel}"
            f"-cp3{py_minor}-cp3{py_minor}-linux_x86_64.whl"
        )
        rewritten_specs.append(f"{spec}@{wheel_url}")

    return rewritten_specs

def _resolve_exact_version(specifier: SpecifierSet) -> Optional[str]:
    """Return the natten version pinned by `==X.Y.Z` in `specifier`, if any.

    natten's per-torch wheel URLs demand a concrete version, so we only accept
    a `==` pin on a version present in `_NATTEN_VERSION_MATRIX`. Any other
    specifier form (range, no version, unknown pin) returns None so the caller
    passes the spec through unchanged.
    """
    if specifier is None:
        return None

    for entry in specifier:
        if entry.operator == "==" and entry.version in _NATTEN_VERSION_MATRIX:
            return entry.version

    return None

def _pick_cuda_channel(
    cuda_channels: List[Tuple[Tuple[int, int], str]],
    cuda_version: Tuple[int, int],
) -> Optional[str]:
    """Return the highest wheel channel whose minimum driver CUDA is satisfied."""
    for min_driver, channel in cuda_channels:
        if min_driver <= cuda_version:
            return channel

    return None

def _parse_requirement(spec: str) -> Optional[Requirement]:
    try:
        return Requirement(spec)
    except Exception:
        return None
