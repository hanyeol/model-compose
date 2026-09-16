from typing import Optional, Tuple, List, Dict, Union
from pathlib import Path
from packaging.requirements import Requirement, SpecifierSet
from packaging.utils import canonicalize_name
from packaging.version import Version, InvalidVersion
from importlib.metadata import version, metadata, PackageNotFoundError
from mindor.core.utils.github import download_github_tarball
import mindor
import sys, subprocess, shutil, importlib, importlib.util, tempfile
import asyncio, re

# The directory that hosts the running `mindor` package — site-packages root
# under a normal install, or `src/` under an editable install. Custom services
# that need to drop an ad-hoc package alongside `mindor` (rename-and-install
# patterns for upstream repos that ship as a bare `src/`) copy into this root
# so the new package becomes importable without touching `sys.path`.
_MINDOR_INSTALL_ROOT: Path = Path(mindor.__file__).resolve().parent.parent

async def install_package(package_spec: str, pip_options: Optional[List[str]] = None) -> None:
    """Install `package_spec` into the running interpreter via pip or uv.

    `package_spec` follows pip syntax — a versioned requirement
    (`"torch>=2.0.0"`), a direct URL (`"git+https://github.com/..."`), a local
    path, or any other spec pip accepts. `pip_options` appends extra flags
    such as `["--index-url", "https://download.pytorch.org/whl/cu128"]`.

    Prefers uv when the current interpreter has no `pip` module available
    (uv installs are faster and skip the pip bootstrap); otherwise falls back
    to `python -m pip install`. Either way, the install targets
    `sys.executable`, so the package is importable in the same process.
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
    subdirs: Optional[List[Union[str, Tuple[str, str]]]] = None,
) -> None:
    """Download a GitHub repo tarball and install selected subdirs as top-level packages.

    Each `subdirs` entry is either a package name (used as both source and
    target) or a `(package_name, source_path)` tuple that renames the copied
    subdirectory. Renamed entries also get their internal `import`/`from`
    references to the original top rewritten to the new name.
    """
    packages = subdirs or [ module_name ]
    clone_dir = Path(tempfile.gettempdir()) / "mindor-git-sources" / module_name

    if not clone_dir.exists():
        clone_dir.parent.mkdir(parents=True, exist_ok=True)
        await download_github_tarball(repo_url, revision, clone_dir)

    for package in packages:
        if isinstance(package, tuple):
            package_name, source_path = package
        else:
            package_name, source_path = package, package

        source = clone_dir / source_path
        target = _MINDOR_INSTALL_ROOT / package_name

        if not source.exists():
            raise FileNotFoundError(f"Package source '{source_path}' not found in downloaded repo at {clone_dir}")

        if not target.exists():
            shutil.copytree(source, target)

            # `source_path == "."` means the repo root is the package — there
            # is no original top-level module name to rewrite. Skip the rewrite
            # in that case; callers that rely on the repo root being on sys.path
            # (e.g. because upstream uses `from models import ...` style
            # top-level imports) are expected to insert it themselves at load time.
            parts = Path(source_path).parts
            top_module = parts[0] if parts else None

            if top_module is not None and top_module != package_name:
                rewrite_python_imports(target, { top_module: package_name })

    importlib.invalidate_caches()

def rewrite_python_imports(root: Path, mapping: Dict[str, str]) -> None:
    """Rewrite top-level import names inside every `.py` file under `root`.

    For each `old -> new` pair, replaces occurrences of `import old[.…]` and
    `from old[.…] import …` at the start of any line (allowing leading
    whitespace). Rewriting is line-anchored and word-bounded so identifiers
    that merely share a prefix with `old` (e.g. `srcutil`) are left untouched.
    """
    patterns: List[Tuple[re.Pattern[str], str]] = []

    for old, new in mapping.items():
        old_escaped = re.escape(old)
        patterns.append((re.compile(rf"(?m)^(\s*import\s+){old_escaped}(\b)"), rf"\1{new}\2"))
        patterns.append((re.compile(rf"(?m)^(\s*from\s+){old_escaped}(\b)"), rf"\1{new}\2"))

    for path in root.rglob("*.py"):
        try:
            source = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        rewritten = source

        for pattern, replacement in patterns:
            rewritten = pattern.sub(replacement, rewritten)

        if rewritten != source:
            path.write_text(rewritten, encoding="utf-8")

def parse_requirement(package_spec: str) -> Optional[Requirement]:
    """Parse `package_spec` as a PEP 508 requirement.

    Returns None when the spec is not a valid PEP 508 requirement — for example
    direct URLs (`"git+https://..."`) or local paths — so callers can distinguish
    "not a versioned dependency" from a parse error.
    """
    try:
        return Requirement(package_spec)
    except Exception:
        return None

def is_requirement_satisfied(requirement: Requirement, repository: Optional[str] = None) -> bool:
    """Check whether the installed distribution satisfies `requirement`.

    Returns False when the package is not installed at all, when its version
    falls outside the specifier, or when any of the requested extras are
    themselves unsatisfied.

    When `repository` names a PyTorch wheel channel (e.g. `.../whl/cu126`),
    the installed distribution's local version segment (e.g. `2.11.0+cu128`)
    is also compared against the channel. A mismatch marks the requirement
    unsatisfied so the caller reinstalls from the requested channel — this
    catches the case where torch and its siblings were installed from
    different CUDA channels and are now ABI-incompatible.
    """
    distribution_name = canonicalize_name(requirement.name)

    try:
        installed_version = version(distribution_name)  # e.g. "4.41.2"
    except PackageNotFoundError:
        return False

    specifier: SpecifierSet = requirement.specifier

    if specifier and not specifier.contains(installed_version, prereleases=True):
        return False

    if requirement.extras and not is_extra_requirement_satisfied(requirement):
        return False

    if not _is_local_version_compatible(installed_version, repository):
        return False

    return True

def _is_local_version_compatible(installed_version: str, repository: Optional[str]) -> bool:
    """Return False when the installed local segment names a different CUDA channel.

    Wheels from `.../whl/cu126/` embed `+cu126` in their version. If the caller
    routes to a different channel (e.g. cu128), reinstalling is the only way to
    swap the CUDA build — pip won't touch a same-version distribution otherwise.
    Falls through (returns True) when either side lacks a channel token, so
    non-torch packages and CPU wheels don't trigger spurious reinstalls.
    """
    if repository is None:
        return True

    requested_channel = _extract_channel(repository)

    if requested_channel is None:
        return True

    try:
        installed_local = Version(installed_version).local
    except InvalidVersion:
        return True

    if not installed_local:
        return True

    return installed_local == requested_channel

def _extract_channel(repository: str) -> Optional[str]:
    """Pull the wheel-index channel token (`cu126`, `cpu`, ...) out of a URL."""
    match = re.search(r"/whl/([^/]+)/?$", repository)
    return match.group(1) if match else None

def is_extra_requirement_satisfied(requirement: Requirement) -> bool:
    """Check whether the extras listed on `requirement` have their dependencies installed.

    Base version and existence are the caller's job — this function only walks
    the `Requires-Dist` entries gated by `extra == "..."` markers and verifies
    each of those dependencies is itself satisfied. Returns False if any is
    missing or if the target package's metadata cannot be read.
    """
    distribution_name = canonicalize_name(requirement.name)

    try:
        requires_dist = metadata(distribution_name).get_all("Requires-Dist") or []
    except PackageNotFoundError:
        return False

    requested_extras = { canonicalize_name(extra) for extra in requirement.extras }

    for dependency_spec in requires_dist:
        try:
            dependency = Requirement(dependency_spec)
        except Exception:
            continue

        if dependency.marker is None:
            continue

        if not any(dependency.marker.evaluate({ "extra": extra }) for extra in requested_extras):
            continue

        if not is_requirement_satisfied(dependency):
            return False

    return True

def remove_requirement(requirements: List[str], package_name: str) -> Optional[str]:
    """Remove the first spec in `requirements` that targets `package_name` and return it.

    Matches on canonicalized distribution names rather than raw prefixes so
    `transformers` doesn't accidentally strip `transformers-foo`. Mutates
    `requirements` in place; returns None when no matching spec is present.
    """
    canonical_name = canonicalize_name(package_name)

    for index, spec in enumerate(requirements):
        requirement = parse_requirement(spec)

        if requirement and canonicalize_name(requirement.name) == canonical_name:
            return requirements.pop(index)

    return None

def get_mindor_install_root() -> Path:
    return _MINDOR_INSTALL_ROOT
