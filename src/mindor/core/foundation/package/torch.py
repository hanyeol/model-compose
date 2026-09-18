from typing import Optional, List, Tuple, Dict, Iterable
from importlib.metadata import PackageNotFoundError, version as _get_installed_version
from packaging.requirements import Requirement
from packaging.version import InvalidVersion, Version
from packaging.specifiers import SpecifierSet
from mindor.core.logger import logging
from .cuda import get_cuda_driver_version
import functools

# torch → paired sibling versions. Keep in sync with pytorch.org/get-started/
# previous-versions/. When a torch version has no explicit entry, sibling
# resolution falls back to the highest tabled version that is <= the requested
# torch (see `_resolve_sibling_version`) — this covers packages that stopped
# releasing paired versions and instead declared forward compatibility, such
# as torchaudio 2.11.0 which is ABI-stable with later torch releases.

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

    Reuses the already-installed torch when it satisfies the caller's spec and
    its embedded CUDA channel (`+cuXXX`) is compatible with the driver — the
    returned specs then carry only the wheel index URL, no exact pin, so
    `is_requirement_satisfied` treats the existing distribution as good and
    pip skips the reinstall (this keeps user-managed torch versions such as
    2.14 in place even when the pin table lags behind upstream).

    Otherwise picks the largest tabled torch version that satisfies the
    caller's constraint and is buildable against the driver, and hard-pins
    torch (and sibling packages) to that release. Torchaudio/torchvision
    follow torch's release triple unless the caller pins them explicitly;
    caller pins are always kept and a warning is logged on mismatch.

    When no CUDA channel serves the requested torch version, falls back to
    the CPU wheel index while preserving the caller's constraints (pip
    resolves the final version against the CPU index).

    Returns specs unchanged on hosts other than Linux x86_64/aarch64 or when
    no NVIDIA driver is detected.
    """
    cuda_version = get_cuda_driver_version()

    if cuda_version is None:
        return list(specs)

    torch_specifier = _get_torch_specifier(specs)
    torch_siblings = _get_torch_siblings(specs)
    resolved_torch = _resolve_torch_and_channel(torch_specifier, torch_siblings, cuda_version)

    if resolved_torch is None:
        logging.warning(
            f"No CUDA wheel channel available for {torch_specifier or 'torch (any)'} "
            f"on driver CUDA {cuda_version[0]}.{cuda_version[1]}; falling back to "
            f"the CPU wheel index while preserving the caller's constraints."
        )
        return _rewrite_specs(specs, None, _CPU_CHANNEL, use_exact_version=False)

    torch_version, channel, use_exact_version = resolved_torch
    logging.info(
        f"Resolved torch{'==' if use_exact_version else '>='}{torch_version} on channel {channel} "
        f"for driver CUDA {cuda_version[0]}.{cuda_version[1]}."
    )

    return _rewrite_specs(specs, torch_version, channel, use_exact_version=use_exact_version)

def _resolve_torch_and_channel(
    torch_specifier: Optional[SpecifierSet],
    torch_siblings: List[str],
    cuda_version: Tuple[int, int],
) -> Optional[Tuple[str, str, bool]]:
    """Pick (torch_version, wheel channel, whether to hard-pin torch).

    Prefers the already-installed torch when it satisfies the caller's
    specifier and its embedded CUDA channel (`+cuXXX`) is compatible with the
    driver — this avoids downgrading a user-managed torch install just because
    the pin table lags behind upstream. When reusing the installed build we
    return `use_exact_version=False` so `_rewrite_specs` leaves the caller's spec
    unpinned and pip treats the existing distribution as already-satisfied.
    Falls through to the tabled resolution (largest matrix version that fits
    the driver) when no installed torch is reusable.
    """
    reusable_torch = _get_reusable_installed_torch(torch_specifier, cuda_version)

    if reusable_torch is not None:
        installed_version, channel = reusable_torch

        if all(_resolve_sibling_version(sibling, installed_version) is not None for sibling in torch_siblings):
            return installed_version, channel, False

    for version in _candidate_torch_versions(torch_specifier):
        if not all(_resolve_sibling_version(sibling, version) is not None for sibling in torch_siblings):
            continue

        channel = _pick_channel_for_cuda_driver(version, cuda_version)

        if channel is not None:
            return version, channel, True

    return None

def _resolve_sibling_version(sibling: str, torch_version: str) -> Optional[str]:
    """Return the sibling release paired with `torch_version`.

    Prefers an exact entry in the sibling table; otherwise falls back to the
    highest tabled version whose paired torch is <= `torch_version`. The
    fallback covers packages that stopped shipping same-cadence releases and
    declared forward compatibility instead (e.g. torchaudio 2.11.0), so a new
    torch release doesn't require editing the sibling table.
    """
    table = _TORCH_SIBLING_TABLES[sibling]
    exact = table.get(torch_version)

    if exact is not None:
        return exact

    torch_key = Version(torch_version)
    candidates = [ tabled for tabled in table if Version(tabled) <= torch_key ]

    if not candidates:
        return None

    return table[max(candidates, key=Version)]

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

def _candidate_torch_versions(torch_specifier: Optional[SpecifierSet]) -> List[str]:
    if torch_specifier is None:
        return _TORCH_VERSIONS_DESC

    return [ version for version in _TORCH_VERSIONS_DESC if torch_specifier.contains(version, prereleases=True) ]

def _get_reusable_installed_torch(
    torch_specifier: Optional[SpecifierSet],
    cuda_version: Tuple[int, int],
) -> Optional[Tuple[str, str]]:
    """Return (version, channel) for the installed torch when it is reusable.

    Reusable means: (1) torch is importable, (2) it exposes a CUDA local tag
    like `+cu128`, and (3) it satisfies the caller's specifier if any.
    Out-of-matrix versions (e.g. torch 2.14 when the table stops at 2.13) are
    still eligible — sibling resolution falls back to the highest tabled entry,
    and the channel comes from the installed local tag rather than the matrix.

    A driver that cannot run the installed channel (e.g. driver 11.8 with a
    cu128 build) does NOT disqualify the install — the user may have staged
    the higher-CUDA build intentionally (portable env, upcoming driver
    upgrade, CPU-only fallback via `torch.cuda.is_available() == False`).
    We log a warning and reuse the install rather than silently downgrading
    a user-managed environment.
    """
    installed_torch = _get_installed_torch_spec()

    if installed_torch is None:
        return None

    version, channel = installed_torch

    if channel is None or channel == _CPU_CHANNEL:
        return None

    if torch_specifier is not None and not torch_specifier.contains(version, prereleases=True):
        return None

    min_driver = _min_cuda_driver_for_channel(channel)

    if min_driver is not None and min_driver > cuda_version:
        logging.warning(
            f"The installed torch {version}+{channel} needs CUDA {min_driver[0]}.{min_driver[1]} or newer, "
            f"but your NVIDIA driver only supports up to CUDA {cuda_version[0]}.{cuda_version[1]}. "
            f"GPU may be unavailable — update the driver or reinstall torch with a build that matches it."
        )

    if version not in _CUDA_CHANNELS_FOR_TORCH:
        logging.warning(
            f"The installed torch {version} is newer than the versions with known-good sibling "
            f"(torchaudio/torchvision/torchcodec) mappings; using best-effort matches. If a sibling "
            f"install fails, reinstall torch to a version with tested pairings."
        )

    return version, channel

@functools.lru_cache(maxsize=1)
def _get_installed_torch_spec() -> Optional[Tuple[str, Optional[str]]]:
    """Return (version, local_tag) for the installed torch, or None if absent.

    `local_tag` is the CUDA channel embedded in the wheel version (e.g.
    `cu128` from `2.8.0+cu128`), or None when the installed build has no
    local segment (source builds, CPU wheels without a tag).
    """
    try:
        version = _get_installed_version("torch")
    except PackageNotFoundError:
        return None

    try:
        version = Version(version)
    except InvalidVersion:
        return None

    return f"{version.major}.{version.minor}.{version.micro}", version.local

def _pick_channel_for_cuda_driver(
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

def _min_cuda_driver_for_channel(channel: str) -> Optional[Tuple[int, int]]:
    """Look up the minimum driver CUDA version required by a wheel channel.

    Scans the matrix for any entry that lists `channel`; all such entries
    agree on the minimum driver because a channel like `cu128` has a fixed
    CUDA runtime requirement independent of the torch version that ships it.
    """
    for channels in _CUDA_CHANNELS_FOR_TORCH.values():
        for min_driver, tabled_channel in channels:
            if tabled_channel == channel:
                return min_driver

    return None

def _rewrite_specs(
    specs: Iterable[str],
    torch_version: Optional[str],
    channel: str,
    use_exact_version: bool,
) -> List[str]:
    """Attach `@<wheel index>` to every torch-family spec.

    When `use_exact_version` is True, unpinned specs are hardened to `==<torch_version>`
    (or the paired sibling release) so pip installs the exact resolved build.
    When False, unpinned specs stay unpinned — used when we intentionally
    reuse an already-installed torch and don't want to trigger a reinstall.
    Caller-provided pins are always preserved, with a warning on sibling
    mismatch against the resolved torch.
    """
    index_url = f"{_WHEEL_INDEX_BASE}/{channel}"
    local_tag = channel if channel != _CPU_CHANNEL else None
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
            if caller_specifier:
                resolved_specifier = _attach_local_tag(caller_specifier, local_tag)
            elif use_exact_version and torch_version:
                resolved_specifier = _attach_local_tag(f"=={torch_version}", local_tag)
            else:
                resolved_specifier = ""
            rewritten_specs.append(f"{name_with_extras}{resolved_specifier}{marker_suffix}@{index_url}")
            continue

        sibling_version = _resolve_sibling_version(requirement.name, torch_version) if torch_version else None

        if caller_specifier:
            if sibling_version is not None and not requirement.specifier.contains(sibling_version, prereleases=True):
                logging.warning(
                    f"{requirement.name}{requirement.specifier} does not match the "
                    f"paired release for torch=={torch_version} "
                    f"({requirement.name}=={sibling_version}); keeping the caller's pin."
                )
            resolved_specifier = _attach_local_tag(caller_specifier, local_tag)
            rewritten_specs.append(f"{name_with_extras}{resolved_specifier}{marker_suffix}@{index_url}")
            continue

        if use_exact_version and sibling_version:
            resolved_specifier = _attach_local_tag(f"=={sibling_version}", local_tag)
        else:
            resolved_specifier = ""

        rewritten_specs.append(f"{name_with_extras}{resolved_specifier}{marker_suffix}@{index_url}")

    return rewritten_specs

def _attach_local_tag(specifier: str, local_tag: Optional[str]) -> str:
    """Append `+local_tag` to a single `==X.Y.Z` pin when not already present.

    Pins the CUDA build so pip picks the intended `2.13.0+cu126` even when
    another local tag (e.g. `+cu130`) is available in the same index. Skips
    non-exact specifiers, ranges, wildcard pins (PEP 440 forbids combining
    `==X.Y.*` with a local version), or pins that already carry a local
    segment. The caller's intent is preserved verbatim in every skipped case
    so pip's own resolver can pick a wheel from the index.
    """
    if local_tag is None or not specifier.startswith("=="):
        return specifier

    version_spec = specifier[2:]

    if "," in version_spec or "+" in version_spec or "*" in version_spec:
        return specifier

    return f"=={version_spec}+{local_tag}"

def _parse_requirement(spec: str) -> Optional[Requirement]:
    try:
        return Requirement(spec)
    except Exception:
        return None
