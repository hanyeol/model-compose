from typing import Optional, List, Tuple, Dict
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version
from mindor.core.logger import logging
from .cuda import is_cuda_installed
from .torch import resolve_torch_build
import sys, platform, re

# flash-attn ships pre-built wheels only via GitHub releases. PyPI has just the
# sdist, whose setup.py imports torch at module level: under pip/uv's default
# build isolation it fails before compiling anything, and with
# `--no-build-isolation` it turns into a long nvcc build that also needs a CUDA
# toolkit with the same major as torch's CUDA build. Each wheel encodes the
# (torch major.minor, CUDA major, cxx11abi, python minor, arch) tuple it was
# built against — the runtime torch install must match exactly.
#
# The target torch comes from `resolve_torch_build`, i.e. the same build
# (version + CUDA channel) that `torch_requirements` installs or reuses, so the
# flash-attn ABI follows the torch that actually lands in the environment.
#
# Wheel sources, tried in order:
#
#   1. Upstream (Dao-AILab) release assets, spread over two tags:
#        v2.8.3.post1 — cu12 x torch 2.4–2.8 (x86_64 only), plus cu13 x torch
#                       2.9 cp312 (x86_64 + aarch64, file version 2.8.3)
#        v2.8.3       — cu12 x torch 2.9 and cu13 x torch 2.10, cp312
#                       (x86_64 + aarch64)
#      v2.8.3.post2 only re-ships x86_64 cu12 x torch 2.4–2.8 and is not tabled.
#   2. On aarch64 only, the community builds of
#      mjun0812/flash-attention-prebuild-wheels (GitHub-hosted ubuntu-22.04-arm
#      runners, torch from download.pytorch.org), matched on the exact torch
#      CUDA channel. Upstream has nothing for aarch64 below torch 2.9 and only
#      cp312 above it; this fills that gap.
#
# Neither source has an aarch64 wheel for torch 2.8. Wheels built with CUDA
# >= 12.8 carry sm_120 SASS, which also runs on GB10 (DGX Spark, sm_121);
# cu126 builds stop at sm_90. Combos outside both tables return the spec
# unchanged so pip attempts its own resolution (the sdist path above; callers
# who cannot afford that fallback should filter the result and drop the spec).

_FLASH_ATTN_PACKAGE_NAME = "flash-attn"

_FLASH_ATTN_RELEASE_BASE = "https://github.com/Dao-AILab/flash-attention/releases/download"
_FLASH_ATTN_COMMUNITY_RELEASE_BASE = "https://github.com/mjun0812/flash-attention-prebuild-wheels/releases/download"

# (torch minor, CUDA major) → upstream wheel entry:
#   (release_tag, version, cxx11abi, python_minors, archs)
# `version` is the version in the file name — differs from the tag for the
# torch 2.9+ assets. Cross-checked against the v2.8.3 / v2.8.3.post1 release
# asset lists.
_FLASH_ATTN_WHEELS: Dict[Tuple[str, str], Tuple[str, str, str, Tuple[int, ...], Tuple[str, ...]]] = {
    ("2.4",  "12"): ("v2.8.3.post1", "2.8.3.post1", "FALSE", (9, 10, 11, 12),     ("x86_64",)),
    ("2.5",  "12"): ("v2.8.3.post1", "2.8.3.post1", "FALSE", (9, 10, 11, 12, 13), ("x86_64",)),
    ("2.6",  "12"): ("v2.8.3.post1", "2.8.3.post1", "FALSE", (9, 10, 11, 12, 13), ("x86_64",)),
    ("2.7",  "12"): ("v2.8.3.post1", "2.8.3.post1", "FALSE", (9, 10, 11, 12, 13), ("x86_64",)),
    ("2.8",  "12"): ("v2.8.3.post1", "2.8.3.post1", "FALSE", (9, 10, 11, 12, 13), ("x86_64",)),
    ("2.9",  "12"): ("v2.8.3",       "2.8.3",       "TRUE",  (12,),               ("x86_64", "aarch64")),
    ("2.9",  "13"): ("v2.8.3.post1", "2.8.3",       "TRUE",  (12,),               ("x86_64", "aarch64")),
    ("2.10", "13"): ("v2.8.3",       "2.8.3",       "TRUE",  (12,),               ("x86_64", "aarch64")),
}

# (arch, torch minor, torch CUDA channel) → list of community wheel entries:
#   (release_tag, version, python_minors)
# One entry per release tag (a few torch/python cells were published under
# different tags). Derived from doc/packages.md of
# mjun0812/flash-attention-prebuild-wheels (bc11b19), keeping only cells whose
# CUDA channel torch itself ships and skipping free-threaded (cp313t/cp314t)
# builds.
_FLASH_ATTN_COMMUNITY_WHEELS: Dict[Tuple[str, str, str], List[Tuple[str, str, Tuple[int, ...]]]] = {
    ("aarch64", "2.5",  "cu124"): [ ("v0.6.4",  "2.8.3", (10, 11, 12)) ],
    ("aarch64", "2.7",  "cu128"): [ ("v0.6.4",  "2.8.3", (10, 11, 12)) ],
    ("aarch64", "2.9",  "cu126"): [ ("v0.7.16", "2.8.3", (10, 11, 12, 13, 14)) ],
    ("aarch64", "2.9",  "cu128"): [ ("v0.7.16", "2.8.3", (10, 11, 12, 13, 14)) ],
    ("aarch64", "2.9",  "cu130"): [ ("v0.7.16", "2.8.3", (10, 11, 12, 13, 14)) ],
    ("aarch64", "2.10", "cu126"): [ ("v0.7.16", "2.8.3", (10, 11, 12, 13, 14)) ],
    ("aarch64", "2.10", "cu128"): [ ("v0.7.16", "2.8.3", (10, 11, 12, 13, 14)) ],
    ("aarch64", "2.10", "cu130"): [ ("v0.7.16", "2.8.3", (10, 11, 12, 13, 14)) ],
    ("aarch64", "2.11", "cu126"): [ ("v0.9.22", "2.8.3", (10, 11, 12, 13, 14)) ],
    ("aarch64", "2.11", "cu128"): [ ("v0.9.22", "2.8.3", (10, 11, 12, 13, 14)) ],
    ("aarch64", "2.11", "cu130"): [ ("v0.9.22", "2.8.3", (10, 11, 12, 13, 14)) ],
    ("aarch64", "2.12", "cu126"): [ ("v0.9.22", "2.8.3", (10, 11, 12, 13, 14)) ],
    ("aarch64", "2.12", "cu130"): [ ("v0.9.22", "2.8.3", (10, 11, 12, 13, 14)) ],
    ("aarch64", "2.12", "cu132"): [ ("v0.9.22", "2.8.3", (10, 11, 12, 13, 14)) ],
    ("aarch64", "2.13", "cu126"): [ ("v0.9.49", "2.8.3", (10, 11, 13, 14)), ("v0.9.48", "2.8.3", (12,)) ],
    ("aarch64", "2.13", "cu130"): [ ("v0.9.49", "2.8.3", (10, 11, 13, 14)), ("v0.9.48", "2.8.3", (12,)) ],
    ("aarch64", "2.13", "cu132"): [ ("v0.9.49", "2.8.3", (10, 11, 13, 14)), ("v0.9.48", "2.8.3", (12,)) ],
    ("aarch64", "2.14", "cu126"): [ ("v0.10.1", "2.8.3", (10, 11, 12, 13, 14)) ],
    ("aarch64", "2.14", "cu130"): [ ("v0.10.1", "2.8.3", (10, 11, 12, 13, 14)) ],
    ("aarch64", "2.14", "cu132"): [ ("v0.10.1", "2.8.3", (10, 11, 12, 13, 14)) ],
}

# Pins that a differently-versioned wheel may serve because the releases differ
# only in packaging: v2.8.3 → v2.8.3.post1 touched setup.py's prebuilt-wheel
# selection and nothing else, so `==2.8.3.post1` can take the `2.8.3` assets
# published for torch 2.9/2.10 and aarch64. 2.8.3.post2 is deliberately absent —
# it backports a torch.load CVE fix and a backward-kernel int32 overflow fix.
_EQUIVALENT_VERSIONS: Dict[str, Tuple[str, ...]] = {
    "2.8.3.post1": ("2.8.3",),
}

def flash_attn_requirements(torch_spec: str, *specs: str) -> List[str]:
    """Attach a pre-built GitHub wheel URL to each flash-attn spec.

    `torch_spec` names the torch build that flash-attn must match (e.g.
    `"torch==2.8.*"` or `"torch>=2.9,<2.10"`) — pass the same torch spec given
    to `torch_requirements`. It is resolved through `resolve_torch_build`, so
    the wheel targets the exact torch version and CUDA channel that gets
    installed (or reused). Callers typically chain this after (or alongside)
    `torch_requirements(torch_spec)` and hand the concatenated list to the
    installer.

    Covers Linux x86_64 and aarch64 hosts with a working NVIDIA driver. When
    the matching wheel's version is a packaging-only twin of the caller's pin
    (`==2.8.3.post1` vs the `2.8.3` torch 2.9+/aarch64 assets), the pin is
    rewritten to the wheel's version so the installed distribution keeps
    satisfying the requirement on later setups.

    Returns specs unchanged on other hosts, when torch resolves to no CUDA
    build, or when no tabled wheel fits the (torch, CUDA, python, arch) combo
    and the caller's pin. pip then falls back to its own resolution, which for
    flash-attn means the sdist described in the module comment.
    """
    arch = _get_wheel_arch()

    if arch is None or not is_cuda_installed():
        return list(specs)

    torch_version, channel = resolve_torch_build(torch_spec)
    torch_minor = _get_torch_minor(torch_version) if torch_version is not None else None
    cuda_major  = _get_cuda_major(channel) if channel is not None else None

    py_minor = sys.version_info.minor
    candidates: List[Tuple[str, str, str]] = []

    if torch_minor is not None and cuda_major is not None:
        candidates = _find_supported_wheels(arch, torch_minor, cuda_major, channel, py_minor)

    target_build = f"torch {torch_version or '(unresolved)'}+{channel or 'none'}, python 3.{py_minor}, {arch}"
    rewritten_specs: List[str] = []

    for spec in specs:
        requirement = _parse_requirement(spec)

        if requirement is None or canonicalize_name(requirement.name) != _FLASH_ATTN_PACKAGE_NAME or requirement.url is not None:
            rewritten_specs.append(spec)
            continue

        rewritten_specs.append(_rewrite_wheel_spec(spec, requirement, candidates, target_build))

    return rewritten_specs

def _rewrite_wheel_spec(spec: str, requirement: Requirement, candidates: List[Tuple[str, str, str]], target_build: str) -> str:
    """Pair `spec` with the first candidate its version pin accepts, or return it unchanged."""
    for url, version, source in candidates:
        matched_spec = _match_spec_to_wheel(spec, requirement, version)

        if matched_spec is None:
            continue

        if matched_spec != spec:
            logging.info(
                f"Installing flash-attn {version} for '{spec}' ({target_build}): the only "
                f"pre-built wheel for this combo is the packaging-identical {version} release."
            )

        if source == "community":
            logging.info(f"Using a community-built flash-attn wheel for {target_build}: {url}")

        return f"{matched_spec}@{url}"

    logging.warning(
        f"No pre-built flash-attn wheel matches '{spec}' for {target_build}; leaving the spec unresolved. "
        f"pip will try the sdist, which needs torch importable at build time (--no-build-isolation) "
        f"and a CUDA toolkit with the same major version as torch's CUDA build."
    )

    return spec

def _find_supported_wheels(
    arch: str,
    torch_minor: str,
    cuda_major: str,
    channel: str,
    py_minor: int,
) -> List[Tuple[str, str, str]]:
    """List the tabled wheels for this combo, upstream first. Each entry is (url, version, source)."""
    candidates: List[Tuple[str, str, str]] = []
    upstream = _FLASH_ATTN_WHEELS.get((torch_minor, cuda_major))

    if upstream is not None:
        release_tag, version, cxx11abi, python_minors, archs = upstream

        if arch in archs and py_minor in python_minors:
            url = (
                f"{_FLASH_ATTN_RELEASE_BASE}/{release_tag}/"
                f"flash_attn-{version}+cu{cuda_major}torch{torch_minor}cxx11abi{cxx11abi}"
                f"-cp3{py_minor}-cp3{py_minor}-linux_{arch}.whl"
            )
            candidates.append((url, version, "upstream"))

    for release_tag, version, python_minors in _FLASH_ATTN_COMMUNITY_WHEELS.get((arch, torch_minor, channel), []):
        if py_minor in python_minors:
            url = (
                f"{_FLASH_ATTN_COMMUNITY_RELEASE_BASE}/{release_tag}/"
                f"flash_attn-{version}+{channel}torch{torch_minor}"
                f"-cp3{py_minor}-cp3{py_minor}-linux_{arch}.whl"
            )
            candidates.append((url, version, "community"))

    return candidates

def _match_spec_to_wheel(spec: str, requirement: Requirement, wheel_version: str) -> Optional[str]:
    """Return the spec to pair with a `wheel_version` wheel, or None when the caller's pin rules it out."""
    if requirement.specifier.contains(wheel_version, prereleases=True):
        return spec

    clauses = list(requirement.specifier)

    if not clauses:
        return None

    for clause in clauses:
        if clause.operator != "==":
            return None

        if wheel_version not in _EQUIVALENT_VERSIONS.get(clause.version, ()):
            return None

    extras = f"[{','.join(sorted(requirement.extras))}]" if requirement.extras else ""
    marker = f"; {requirement.marker}" if requirement.marker else ""

    return f"{requirement.name}{extras}=={wheel_version}{marker}"

def _get_wheel_arch() -> Optional[str]:
    """Return the wheel arch tag for this host (`x86_64` / `aarch64`), or None when unsupported."""
    if sys.platform == "linux":
        machine = platform.machine()

        if machine in ("x86_64", "aarch64"):
            return machine

    return None

def _get_cuda_major(channel: str) -> Optional[str]:
    """`cu128` → `12`, `cu130` → `13`; None for `cpu` or ROCm channels."""
    match = re.fullmatch(r"cu(\d+)(\d)", channel)

    if match:
        return match.group(1)
    
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
