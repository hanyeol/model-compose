from typing import Optional, List, Tuple, Dict
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version
from mindor.core.logger import logging
from .cuda import is_cuda_installed
from .torch import resolve_torch_build
import sys, platform

# natten ships pre-built wheels only via GitHub releases (mirrored as a find-links
# page at whl.natten.org). PyPI has just the sdist, whose setup.py imports torch
# at module level: under pip/uv's default build isolation it fails with
# `ModuleNotFoundError: No module named 'torch'` before compiling anything, and
# with `--no-build-isolation` it only compiles libnatten when it can see a GPU
# (or NATTEN_CUDA_ARCH is set) — otherwise it quietly installs the
# Flex-Attention-only package.
#
# Each wheel is built against one exact (torch release, CUDA channel, python
# minor, arch) and carries the torch/CUDA part in its local version, e.g.
# `0.21.7+torch2130cu130`, which the installed distribution keeps. The rewritten
# spec pins that full version, so a torch or CUDA-channel change shows up as an
# unsatisfied requirement instead of a stale ABI. The target torch comes from
# `resolve_torch_build` — the build `torch_requirements` installs or reuses — and
# the wheel must match its minor and CUDA channel exactly.
#
# NATTEN publishes wheels for the two newest torch releases at each tag:
#   0.21.0 — torch 2.7 (cu126/cu128), x86_64 only
#   0.21.1 — torch 2.8 (cu126/cu128/cu129, x86_64 only), torch 2.9 (cu126/cu128/cu130)
#   0.21.5 — torch 2.9 and 2.10 (cu126/cu128/cu130)
#   0.21.6 — torch 2.10, 2.11 (cu126/cu128/cu130) and 2.12 (cu126/cu130/cu132)
#   0.21.7 — torch 2.12 and 2.13 (cu126/cu130/cu132)
# aarch64 wheels start at 0.21.1 / torch 2.9, so a `natten==0.21.0` pin cannot be
# served there. cu126 builds stop at sm_90; cu128+ builds include sm_120, which
# GB10 (DGX Spark, sm_121) runs, and 0.21.7 fixes cutlass-fna/fmha config
# selection on SM120/SM121. Combos outside the table return the spec unchanged
# (callers who cannot afford the sdist fallback should filter the result).

_NATTEN_PACKAGE_NAME = "natten"

_NATTEN_RELEASE_BASE = "https://github.com/SHI-Labs/NATTEN/releases/download"

# natten version → torch release the wheels were built against →
#   (CUDA channels, python minors, archs)
# python minors are GIL builds only; free-threaded (cp313t, ...) wheels are skipped.
# Cross-checked against each tag's release asset list.
_NATTEN_WHEELS: Dict[str, Dict[str, Tuple[Tuple[str, ...], Tuple[int, ...], Tuple[str, ...]]]] = {
    "0.21.0": {
        "2.7.0":  (("cu126", "cu128"),          (9, 10, 11, 12),          ("x86_64",)),
    },
    "0.21.1": {
        "2.8.0":  (("cu126", "cu128", "cu129"), (9, 10, 11, 12, 13),      ("x86_64",)),
        "2.9.0":  (("cu126", "cu128", "cu130"), (10, 11, 12, 13),         ("x86_64", "aarch64")),
    },
    "0.21.5": {
        "2.9.0":  (("cu126", "cu128", "cu130"), (10, 11, 12, 13),         ("x86_64", "aarch64")),
        "2.10.0": (("cu126", "cu128", "cu130"), (10, 11, 12, 13, 14),     ("x86_64", "aarch64")),
    },
    "0.21.6": {
        "2.10.0": (("cu126", "cu128", "cu130"), (10, 11, 12, 13, 14),     ("x86_64", "aarch64")),
        "2.11.0": (("cu126", "cu128", "cu130"), (10, 11, 12, 13, 14),     ("x86_64", "aarch64")),
        "2.12.0": (("cu126", "cu130", "cu132"), (10, 11, 12, 13, 14),     ("x86_64", "aarch64")),
    },
    "0.21.7": {
        "2.12.0": (("cu126", "cu130", "cu132"), (10, 11, 12, 13, 14),     ("x86_64", "aarch64")),
        "2.13.0": (("cu126", "cu130", "cu132"), (10, 11, 12, 13, 14, 15), ("x86_64", "aarch64")),
    },
}

def natten_requirements(torch_spec: str, *specs: str) -> List[str]:
    """Attach a pre-built GitHub wheel URL to each natten spec.

    `torch_spec` names the torch build natten must match (e.g. `"torch==2.7.*"`)
    — pass the same torch spec given to `torch_requirements`. It is resolved
    through `resolve_torch_build`, so the wheel targets the exact torch minor and
    CUDA channel that gets installed (or reused).

    The natten spec may be an exact pin (`natten==0.21.0`), a range
    (`natten>=0.21.5`) or bare (`natten`): the highest tabled natten release that
    satisfies it and ships a wheel for this (torch, CUDA channel, python, arch)
    wins. The returned spec pins the wheel's full version, local label included
    (`natten==0.21.0+torch270cu128@<url>`).

    Covers Linux x86_64 and aarch64 hosts with a working NVIDIA driver. Returns
    specs unchanged on other hosts, when torch resolves to no CUDA build, or when
    no tabled wheel fits — pip then falls back to the sdist described in the
    module comment.
    """
    arch = _get_wheel_arch()

    if arch is None or not is_cuda_installed():
        return list(specs)

    torch_version, channel = resolve_torch_build(torch_spec)
    torch_minor = _get_torch_minor(torch_version) if torch_version is not None else None

    py_minor = sys.version_info.minor
    target_build = f"torch {torch_version or '(unresolved)'}+{channel or 'none'}, python 3.{py_minor}, {arch}"

    rewritten_specs: List[str] = []

    for spec in specs:
        requirement = _parse_requirement(spec)

        if requirement is None or canonicalize_name(requirement.name) != _NATTEN_PACKAGE_NAME or requirement.url is not None:
            rewritten_specs.append(spec)
            continue

        wheel = _resolve_wheel_spec(requirement, torch_minor, channel, py_minor, arch) if torch_minor is not None and channel else None

        if wheel is None:
            logging.warning(
                f"No pre-built natten wheel matches '{spec}' for {target_build}; leaving the spec unresolved. "
                f"pip will try the sdist, which needs torch importable at build time (--no-build-isolation) "
                f"and a visible GPU or NATTEN_CUDA_ARCH — without either it installs natten without libnatten "
                f"(Flex Attention backend only)."
            )
            rewritten_specs.append(spec)
            continue

        version, url = wheel
        rewritten_specs.append(f"{_format_requirement(requirement, f'=={version}')}@{url}")

    return rewritten_specs

def _resolve_wheel_spec(
    requirement: Requirement,
    torch_minor: str,
    channel: str,
    py_minor: int,
    arch: str,
) -> Optional[Tuple[str, str]]:
    """Return `(full_version, url)` of the newest tabled wheel the spec accepts, or None."""
    for natten_version in sorted(_NATTEN_WHEELS, key=Version, reverse=True):
        for torch_build, (channels, python_minors, archs) in _NATTEN_WHEELS[natten_version].items():
            if _get_torch_minor(torch_build) != torch_minor:
                continue

            if channel not in channels or py_minor not in python_minors or arch not in archs:
                continue

            local_label = f"torch{torch_build.replace('.', '')}{channel}"
            full_version = f"{natten_version}+{local_label}"

            # Tested with the local label so an already-qualified pin
            # (`==0.21.7+torch2130cu130`) only accepts that exact build.
            if not requirement.specifier.contains(full_version, prereleases=True):
                continue

            # The `+` in the wheel version tag has to be percent-encoded for pip to
            # download the file directly (GitHub Release URLs treat `+` as literal,
            # but pip strips it when parsing the direct URL otherwise).
            url = (
                f"{_NATTEN_RELEASE_BASE}/v{natten_version}/"
                f"natten-{natten_version}%2B{local_label}"
                f"-cp3{py_minor}-cp3{py_minor}-linux_{arch}.whl"
            )

            return full_version, url

    return None

def _get_wheel_arch() -> Optional[str]:
    """Return the wheel arch tag for this host (`x86_64` / `aarch64`), or None when unsupported."""
    if sys.platform == "linux":
        machine = platform.machine()

        if machine in ("x86_64", "aarch64"):
            return machine

    return None

def _get_torch_minor(torch_version: str) -> Optional[str]:
    try:
        version = Version(torch_version)
    except InvalidVersion:
        return None

    return f"{version.major}.{version.minor}"

def _parse_requirement(spec: str) -> Optional[Requirement]:
    try:
        return Requirement(spec)
    except Exception:
        return None

def _format_requirement(requirement: Requirement, specifier: str) -> str:
    extras = f"[{','.join(sorted(requirement.extras))}]" if requirement.extras else ""
    marker = f"; {requirement.marker}" if requirement.marker else ""

    return f"{requirement.name}{extras}{specifier}{marker}"
