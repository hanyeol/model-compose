from typing import Optional, Tuple, List, Dict, Union
from pathlib import Path
from packaging.requirements import Requirement, SpecifierSet
from packaging.utils import canonicalize_name
from importlib.metadata import version, PackageNotFoundError
from mindor.core.utils.github import download_github_tarball
import mindor
import sys, subprocess, shutil, importlib, importlib.util, tempfile
import asyncio, re

# mindor is our own package, so its parent directory is the site-packages root
# (or the src/ folder under an editable install). Placing new package dirs
# there makes them importable without touching sys.path.
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

            top_module = Path(source_path).parts[0]

            if top_module != package_name:
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
            original = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        rewritten = original
        for pattern, repl in patterns:
            rewritten = pattern.sub(repl, rewritten)

        if rewritten != original:
            path.write_text(rewritten, encoding="utf-8")

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
