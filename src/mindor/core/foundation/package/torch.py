from typing import Optional, List, Tuple, Dict, Iterable
from packaging.requirements import Requirement
from packaging.version import Version
from packaging.specifiers import SpecifierSet
from mindor.core.logger import logging
from .cuda import get_cuda_driver_version

# torch → paired sibling versions. Keep both tables in sync with
# pytorch.org/get-started/previous-versions/ — each PyTorch release publishes
# one triple. torchaudio's version currently mirrors torch exactly, but we keep
# a separate map so a future release that breaks that convention shows up as an
# obvious edit rather than a silent bug.
_TORCHAUDIO_FOR_TORCH: Dict[str, str] = {
    "2.11.0": "2.11.0",
    "2.10.0": "2.10.0",
    "2.9.1":  "2.9.1",
    "2.9.0":  "2.9.0",
    "2.8.0":  "2.8.0",
    "2.7.1":  "2.7.1",
    "2.7.0":  "2.7.0",
    "2.6.0":  "2.6.0",
    "2.5.1":  "2.5.1",
    "2.5.0":  "2.5.0",
    "2.4.1":  "2.4.1",
    "2.4.0":  "2.4.0",
}

_TORCHVISION_FOR_TORCH: Dict[str, str] = {
    "2.13.0": "0.28.0",
    "2.12.1": "0.27.1",
    "2.12.0": "0.27.0",
    "2.11.0": "0.26.0",
    "2.10.0": "0.25.0",
    "2.9.1":  "0.24.1",
    "2.9.0":  "0.24.0",
    "2.8.0":  "0.23.0",
    "2.7.1":  "0.22.1",
    "2.7.0":  "0.22.0",
    "2.6.0":  "0.21.0",
    "2.5.1":  "0.20.1",
    "2.5.0":  "0.20.0",
    "2.4.1":  "0.19.1",
    "2.4.0":  "0.19.0",
}

# torchcodec compatibility per https://github.com/pytorch/torchcodec — pinned to
# the highest release that officially supports each torch version.
_TORCHCODEC_FOR_TORCH: Dict[str, str] = {
    "2.11.0": "0.11",
    "2.10.0": "0.10",
    "2.9.1":  "0.9",
    "2.9.0":  "0.9",
    "2.8.0":  "0.7",
    "2.7.1":  "0.5",
    "2.7.0":  "0.5",
    "2.6.0":  "0.2",
    "2.5.1":  "0.1",
    "2.5.0":  "0.1",
    "2.4.1":  "0.0.3",
    "2.4.0":  "0.0.3",
}

_TORCH_SIBLING_TABLES: Dict[str, Dict[str, str]] = {
    "torchaudio":  _TORCHAUDIO_FOR_TORCH,
    "torchvision": _TORCHVISION_FOR_TORCH,
    "torchcodec":  _TORCHCODEC_FOR_TORCH,
}

# torch version → CUDA channels that ship a wheel for it, ordered high-to-low.
# A "channel" pairs a wheel name (cu128) with the minimum driver CUDA version
# it requires (driver must be >= this). Data source: PyTorch previous-versions
# page cross-checked against the actual /whl/<channel>/torch/ indices.
_CUDA_CHANNELS_FOR_TORCH: Dict[str, List[Tuple[Tuple[int, int], str]]] = {
    "2.13.0": [((13, 2), "cu132"), ((13, 0), "cu130"), ((12, 6), "cu126")],
    "2.12.1": [((13, 2), "cu132"), ((13, 0), "cu130"), ((12, 6), "cu126")],
    "2.12.0": [((13, 2), "cu132"), ((13, 0), "cu130"), ((12, 6), "cu126")],
    "2.11.0": [((13, 0), "cu130"), ((12, 8), "cu128"), ((12, 6), "cu126")],
    "2.10.0": [((13, 0), "cu130"), ((12, 8), "cu128"), ((12, 6), "cu126")],
    "2.9.1":  [((13, 0), "cu130"), ((12, 8), "cu128"), ((12, 6), "cu126")],
    "2.9.0":  [((13, 0), "cu130"), ((12, 8), "cu128"), ((12, 6), "cu126")],
    "2.8.0":  [((12, 9), "cu129"), ((12, 8), "cu128"), ((12, 6), "cu126")],
    "2.7.1":  [((12, 8), "cu128"), ((12, 6), "cu126"), ((11, 8), "cu118")],
    "2.7.0":  [((12, 8), "cu128"), ((12, 6), "cu126"), ((11, 8), "cu118")],
    "2.6.0":  [((12, 6), "cu126"), ((12, 4), "cu124"), ((11, 8), "cu118")],
    "2.5.1":  [((12, 4), "cu124"), ((12, 1), "cu121"), ((11, 8), "cu118")],
    "2.5.0":  [((12, 4), "cu124"), ((12, 1), "cu121"), ((11, 8), "cu118")],
    "2.4.1":  [((12, 4), "cu124"), ((12, 1), "cu121"), ((11, 8), "cu118")],
    "2.4.0":  [((12, 4), "cu124"), ((12, 1), "cu121"), ((11, 8), "cu118")],
}

_WHEEL_INDEX_BASE = "https://download.pytorch.org/whl"
_CPU_CHANNEL = "cpu"

# torch versions ordered high-to-low, used to pick the largest version that
# satisfies a `>=X` / range spec on a given CUDA channel.
_TORCH_VERSIONS_DESC: List[str] = sorted(
    _CUDA_CHANNELS_FOR_TORCH.keys(),
    key=Version,
    reverse=True,
)

_TORCH_PACKAGE_NAMES = frozenset({ "torch", "torchaudio", "torchvision", "torchcodec" })

def torch_requirements(*specs: str) -> List[str]:
    """Attach a PyTorch wheel index to each torch/torchaudio/torchvision spec.

    Picks the largest torch version that satisfies the caller's constraint on
    `torch` and is buildable against the host's NVIDIA driver (via `nvidia-smi`).
    Torchaudio/torchvision follow torch's release triple unless the caller pins
    them explicitly; caller pins are kept and a warning is logged if they do
    not match the paired release.

    When no CUDA channel serves the requested torch version, falls back to the
    CPU wheel index while preserving the caller's constraints (pip resolves the
    final version against the CPU index).

    Returns specs unchanged on non-Linux/x86_64 hosts or when no NVIDIA driver
    is detected.
    """
    cuda_version = get_cuda_driver_version()

    if cuda_version is None:
        return list(specs)

    torch_specifier = _get_torch_specifier(specs)
    torch_siblings = _get_torch_siblings(specs)
    resolution = _resolve_torch_and_channel(torch_specifier, torch_siblings, cuda_version)

    if resolution is None:
        logging.warning(
            f"No CUDA wheel channel available for {torch_specifier or 'torch (any)'} "
            f"on driver CUDA {cuda_version[0]}.{cuda_version[1]}; falling back to "
            f"the CPU wheel index while preserving the caller's constraints."
        )
        return _rewrite_specs(specs, None, _CPU_CHANNEL)

    torch_version, channel = resolution
    logging.info(
        f"Resolved torch=={torch_version} on channel {channel} for driver "
        f"CUDA {cuda_version[0]}.{cuda_version[1]}."
    )

    return _rewrite_specs(specs, torch_version, channel)

def _get_torch_specifier(specs: Iterable[str]) -> Optional[SpecifierSet]:
    for spec in specs:
        requirement = _parse_requirement(spec)

        if requirement is not None and requirement.name == "torch":
            return requirement.specifier if str(requirement.specifier) else None

    return None

def _get_torch_siblings(specs: Iterable[str]) -> List[str]:
    siblings: List[str] = []

    for spec in specs:
        requirement = _parse_requirement(spec)

        if requirement is None or requirement.url is not None:
            continue

        if requirement.name in _TORCH_SIBLING_TABLES and requirement.name not in siblings:
            siblings.append(requirement.name)

    return siblings

def _resolve_torch_and_channel(
    torch_specifier: Optional[SpecifierSet],
    torch_siblings: List[str],
    cuda_version: Tuple[int, int],
) -> Optional[Tuple[str, str]]:
    for version in _candidate_torch_versions(torch_specifier):
        if not all(version in _TORCH_SIBLING_TABLES[sibling] for sibling in torch_siblings):
            continue

        channel = _pick_channel_for_driver(version, cuda_version)

        if channel is not None:
            return version, channel

    return None

def _candidate_torch_versions(torch_specifier: Optional[SpecifierSet]) -> List[str]:
    if torch_specifier is None:
        return _TORCH_VERSIONS_DESC

    return [ version for version in _TORCH_VERSIONS_DESC if torch_specifier.contains(version, prereleases=True) ]

def _pick_channel_for_driver(
    torch_version: str,
    cuda_version: Tuple[int, int],
) -> Optional[str]:
    channels = _CUDA_CHANNELS_FOR_TORCH.get(torch_version)

    if not channels:
        return None

    for min_driver, channel in channels:
        if min_driver <= cuda_version:
            return channel

    return None

def _rewrite_specs(specs: Iterable[str], torch_version: Optional[str], channel: str) -> List[str]:
    index_url = f"{_WHEEL_INDEX_BASE}/{channel}"
    rewritten_specs: List[str] = []

    for spec in specs:
        requirement = _parse_requirement(spec)

        if requirement is None or requirement.name not in _TORCH_PACKAGE_NAMES:
            rewritten_specs.append(spec)
            continue

        if requirement.url is not None:
            rewritten_specs.append(spec)
            continue

        name_with_extras = f"{requirement.name}[{','.join(sorted(requirement.extras))}]" if requirement.extras else requirement.name
        marker_suffix = f"; {requirement.marker}" if requirement.marker else ""
        caller_specifier = str(requirement.specifier)

        if requirement.name == "torch":
            resolved_specifier = caller_specifier or (f"=={torch_version}" if torch_version else "")
            rewritten_specs.append(f"{name_with_extras}{resolved_specifier}{marker_suffix}@{index_url}")
            continue

        sibling_version = _TORCH_SIBLING_TABLES[requirement.name].get(torch_version) if torch_version else None

        if caller_specifier:
            if sibling_version is not None and not requirement.specifier.contains(sibling_version, prereleases=True):
                logging.warning(
                    f"{requirement.name}{requirement.specifier} does not match the "
                    f"paired release for torch=={torch_version} "
                    f"({requirement.name}=={sibling_version}); keeping the caller's pin."
                )
            rewritten_specs.append(f"{name_with_extras}{caller_specifier}{marker_suffix}@{index_url}")
            continue

        resolved_specifier = f"=={sibling_version}" if sibling_version else ""
        rewritten_specs.append(f"{name_with_extras}{resolved_specifier}{marker_suffix}@{index_url}")

    return rewritten_specs

def _parse_requirement(spec: str) -> Optional[Requirement]:
    try:
        return Requirement(spec)
    except Exception:
        return None
