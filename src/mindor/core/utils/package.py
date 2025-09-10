from typing import Optional, Tuple
from packaging.requirements import Requirement, SpecifierSet
from packaging.utils import canonicalize_name
from importlib.metadata import version, PackageNotFoundError
import sys, subprocess, re
import asyncio

async def install_package(package_spec: str) -> None:
    """Install a package using pip.
    
    Args:
        package_spec: Package specification to install (e.g., "torch>=2.0.0" or "git+https://github.com/...")
    """
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "pip", "install", package_spec,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    stdout, stderr = await process.communicate()
    
    if process.returncode != 0:
        raise subprocess.CalledProcessError(
            process.returncode, 
            [sys.executable, "-m", "pip", "install", package_spec],
            output=stdout,
            stderr=stderr
        )

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
