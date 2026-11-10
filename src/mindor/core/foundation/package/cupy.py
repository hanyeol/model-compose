from typing import Optional, Tuple, Dict, List, Iterable
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from mindor.core.logger import logging
from .cuda import get_cuda_driver_version

_CUPY_PACKAGE_NAME = "cupy"

# CuPy ships one distribution per CUDA major; wheels for a given variant only
# resolve on hosts whose driver matches that major. A user-installed variant
# (e.g. the user staged `cupy-cuda11x` on a CUDA 11 host) should satisfy any
# of these distribution names, so we list them as canonical aliases.
_CUPY_DISTRIBUTIONS: List[str] = [
    "cupy",
    "cupy-cuda11x",
    "cupy-cuda12x",
    "cupy-cuda13x",
    "cupy-rocm-5-0",
    "cupy-rocm-4-3",
]

# CUDA driver major → preferred CuPy distribution. Keep the fallback as
# `cupy-cuda12x`: CUDA 12 drivers are the dominant NVIDIA baseline in 2026,
# and the source `cupy` build is reserved for exotic hosts that supply a
# matching CUDA Toolkit themselves.
_CUPY_DISTRIBUTION_FOR_CUDA_MAJOR: Dict[int, str] = {
    11: "cupy-cuda11x",
    12: "cupy-cuda12x",
    13: "cupy-cuda13x",
}

_DEFAULT_CUPY_DISTRIBUTION = "cupy-cuda12x"

def cupy_requirements(*specs: str) -> List[Tuple[str, List[str]]]:
    """Attach the right `cupy-cudaXYx` distribution to each generic `cupy` spec.

    Mirrors `torch_requirements`: callers write a backend-neutral specifier
    like `cupy>=13.6,<14` and the helper picks the distribution name that
    matches the host's NVIDIA driver major (11/12/13). Specs that already
    name a specific CuPy variant (`cupy-cuda11x==13.4`) pass through
    unchanged.

    Each returned entry is `(spec, canonical_names)` so installer checks
    (`is_requirement_satisfied`) accept any already-installed CuPy variant.
    That way a user who staged `cupy-cuda11x` ahead of time isn't forced to
    reinstall `cupy-cuda12x` just because our detection landed on the
    default.

    On non-NVIDIA hosts (macOS, CPU-only Linux, missing nvidia-smi) the
    helper still returns a spec so pip can fail with its own clear error at
    install time; the CuPy launcher itself refuses non-CUDA devices via
    `device.type != "cuda"`, so no caller silently proceeds.
    """
    cuda_version = get_cuda_driver_version()

    if cuda_version is None:
        logging.info(
            f"Resolved CuPy distribution {_DEFAULT_CUPY_DISTRIBUTION} on a host "
            f"without a detectable NVIDIA driver."
        )

        return _rewrite_specs(specs, _DEFAULT_CUPY_DISTRIBUTION)

    distribution = _CUPY_DISTRIBUTION_FOR_CUDA_MAJOR.get(cuda_version[0])

    if distribution is None:
        logging.warning(
            f"No CuPy wheel maps to driver CUDA {cuda_version[0]}.{cuda_version[1]}; "
            f"falling back to {_DEFAULT_CUPY_DISTRIBUTION}. Install may fail — "
            f"consider installing a matching CuPy variant manually."
        )

        return _rewrite_specs(specs, _DEFAULT_CUPY_DISTRIBUTION)

    logging.info(
        f"Resolved CuPy distribution {distribution} for driver "
        f"CUDA {cuda_version[0]}.{cuda_version[1]}."
    )

    return _rewrite_specs(specs, distribution)

def _rewrite_specs(specs: Iterable[str], distribution: str) -> List[Tuple[str, List[str]]]:
    """Attach the CUDA-appropriate CuPy distribution to each generic `cupy` spec.

    Specs that already pin a specific CuPy distribution, that already carry a
    direct URL, or that we couldn't parse pass through verbatim — the caller
    has either made an explicit choice or we shouldn't silently rewrite a
    spec we don't understand.

    Each returned entry is `(spec, canonical_names)` where canonical_names
    lists the other CuPy distribution names so `is_requirement_satisfied`
    accepts an already-installed variant as satisfying the requirement.
    """
    rewritten_specs: List[Tuple[str, List[str]]] = []

    for spec in specs:
        requirement = _parse_requirement(spec)

        if requirement is None or canonicalize_name(requirement.name) != _CUPY_PACKAGE_NAME:
            installed_name = canonicalize_name(requirement.name) if requirement is not None else None
            rewritten_specs.append((spec, [ name for name in _CUPY_DISTRIBUTIONS if name != installed_name ]))

            continue

        if requirement.url is not None:
            rewritten_specs.append((spec, [ name for name in _CUPY_DISTRIBUTIONS if name != _CUPY_PACKAGE_NAME ]))

            continue

        name_with_extras = f"{distribution}[{','.join(sorted(requirement.extras))}]" if requirement.extras else distribution
        marker_suffix = f"; {requirement.marker}" if requirement.marker else ""
        caller_specifier = str(requirement.specifier)

        aliases = [ name for name in _CUPY_DISTRIBUTIONS if name != distribution ]
        rewritten_specs.append((f"{name_with_extras}{caller_specifier}{marker_suffix}", aliases))

    return rewritten_specs

def _parse_requirement(spec: str) -> Optional[Requirement]:
    try:
        return Requirement(spec)
    except Exception:
        return None
