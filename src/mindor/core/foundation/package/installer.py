from typing import Optional, Tuple, List
from pathlib import Path
from packaging.requirements import Requirement, SpecifierSet
from packaging.utils import canonicalize_name
from importlib.metadata import version, PackageNotFoundError
from mindor.core.utils.github import download_github_tarball
import mindor
import sys, subprocess, shutil, importlib, importlib.util, tempfile
import asyncio

# mindor is our own package, so its parent directory is the site-packages root
# (or the src/ folder under an editable install). Placing new package dirs
# there makes them importable without touching sys.path.
_MINDOR_INSTALL_ROOT: Path = Path(mindor.__file__).resolve().parent.parent

async def install_package(package_spec: str, pip_options: Optional[List[str]] = None) -> None:
    """Install a package using pip or uv.

    Args:
        package_spec: Package specification to install (e.g., "torch>=2.0.0" or "git+https://github.com/...")
        pip_options: Additional pip options (e.g., ["--index-url", "https://download.pytorch.org/whl/cu128"])
    """
    uv_path = shutil.which("uv") if importlib.util.find_spec("pip") is None else None

    if uv_path:
        command = [ uv_path, "pip", "install", "--python", sys.executable, package_spec ] + (pip_options or [])
    else:
        command = [ sys.executable, "-m", "pip", "install", package_spec ] + (pip_options or [])

    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        raise subprocess.CalledProcessError(
            process.returncode,
            command,
            output=stdout,
            stderr=stderr
        )

async def install_package_from_github(
    module_name: str,
    repo_url: str,
    revision: Optional[str] = None,
    subdirs: Optional[List[str]] = None,
) -> None:
    """Download `repo_url` as a tarball and copy its packages into site-packages.

    Fetch the repository archive from GitHub (no `git` CLI required), unpack it
    under $TMPDIR/mindor-git-sources/<module_name>, and copy each package
    directory listed in `subdirs` (default: `[module_name]`) into the
    site-packages root alongside the running `mindor` install.

    `revision` pins the download to a specific commit SHA, tag, or branch. The
    default (`None`) fetches the repository's default branch at download time.

    Only GitHub is supported. `repo_url` must resolve to a
    `github.com/<owner>/<repo>` path (with or without a trailing `.git`).
    """
    packages = subdirs or [ module_name ]
    clone_dir = Path(tempfile.gettempdir()) / "mindor-git-sources" / module_name

    if not clone_dir.exists():
        clone_dir.parent.mkdir(parents=True, exist_ok=True)
        await download_github_tarball(repo_url, revision, clone_dir)

    for package in packages:
        source = clone_dir / package
        target = _MINDOR_INSTALL_ROOT / package

        if not source.exists():
            raise FileNotFoundError(f"Package '{package}' not found in downloaded source at {clone_dir}")

        if not target.exists():
            shutil.copytree(source, target)

    importlib.invalidate_caches()

def parse_requirement(package_spec: str) -> Optional[Requirement]:
    """Attempt to parse the package specification as a PEP 508 requirement.

    Args:
        package_spec: A package specification string (e.g., "torch>=2.0.0" or "git+https://github.com/...")

    Returns:
        A Requirement object if the specification can be parsed, None otherwise
    """    
    try:
        return Requirement(package_spec)
    except Exception:
        return None

def is_requirement_satisfied(requirement: Requirement) -> bool:
    """Check whether the installed version of a package satisfies the given requirement.

    Args:
        requirement: Requirement object specifying the package name and version constraints.

    Returns:
        True if the package is installed and its version meets the requirement, False otherwise.
    """
    distribution_name = canonicalize_name(requirement.name)

    try:
        installed_version = version(distribution_name)  # e.g. "4.41.2"
    except PackageNotFoundError:
        return False

    specifier: SpecifierSet = requirement.specifier
    if not specifier:
        return True

    return specifier.contains(installed_version, prereleases=True)
