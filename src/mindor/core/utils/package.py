import sys, subprocess, re
import asyncio

_VERSION_SPEC_PATTERN = re.compile(r'^([a-zA-Z0-9_\-\.]+)([><=!]+.*)?$')

async def install_package(package_spec: str) -> None:
    """Install a package using pip.
    
    Args:
        package_spec: Package specification to install (e.g., "torch>=2.0.0")
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

def extract_module_name(package_spec: str) -> str:
    """Extract module name from package specification.

    Args:
        package_spec: Package specification like "torch>=2.0.0" or "transformers"
        
    Returns:
        Module name for importing (e.g., "torch" from "torch>=2.0.0")
    """
    match = re.match(_VERSION_SPEC_PATTERN, package_spec)
    
    if match:
        return match.group(1)
    
    return None

def is_module_installed(module_name: str) -> bool:
    """Check if a module is installed and importable.
    
    Args:
        module_name: Name of the module to check
        
    Returns:
        True if module can be imported, False otherwise
    """
    try:
        __import__(module_name)
        return True
    except ImportError:
        return False
