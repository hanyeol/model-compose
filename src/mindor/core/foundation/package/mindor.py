"""Utilities for inspecting and packaging the host-installed ``mindor`` package
itself. Peer of ``cuda.py`` / ``torch.py`` / ``flash_attn.py`` under
``foundation/package/``: those modules know how to install specific external
packages; this one knows how to extract the currently running ``mindor``
installation and hand it to an isolated runtime (venv, container, remote pod)."""

from __future__ import annotations

from typing import IO
from mindor.core.utils.archive import archive_to_stream, skip_python_artifacts
from pathlib import Path
import mindor, mindor.version

def package_to_tar(gzipped: bool = True) -> IO[bytes]:
    """Return the host source tree as a (gzipped) tar stream."""
    return archive_to_stream(
        dirs={"mindor": get_root_path()},
        filter=skip_python_artifacts,
        gzipped=gzipped,
    )

def get_root_path() -> Path:
    """Absolute path to the host-installed ``mindor`` package directory."""
    return Path(mindor.__file__).resolve().parent

def get_requirements_path() -> Path:
    """Path to the shipped ``requirements.txt`` for isolated runtime bootstrap."""
    return get_root_path() / "core" / "runtime" / "bootstrap" / "requirements.txt"

def get_version() -> str:
    """Version string from the host-installed ``mindor`` package."""
    return mindor.version.__version__
