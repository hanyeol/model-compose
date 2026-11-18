import os

_APP_NAMESPACE = "mindor"

def xdg_cache_home() -> str:
    """Base user cache dir — ``$XDG_CACHE_HOME`` or ``~/.cache``. Unix-style on
    every platform (matches HuggingFace / PyTorch / Ollama conventions over
    macOS ``~/Library/Caches`` or Windows ``%LOCALAPPDATA%``), so users find
    all AI-tool caches under one root."""
    return os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")

def xdg_data_home() -> str:
    """Base user data dir — ``$XDG_DATA_HOME`` or ``~/.local/share``. For
    persistent data whose loss hurts (venvs, installed tools); kept separate
    from the cache root so disk-cleanup of ``~/.cache`` stays safe."""
    return os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")

def app_cache_dir(*subpaths: str) -> str:
    """App-namespaced cache dir: ``<xdg_cache_home>/mindor/<subpaths>``."""
    return os.path.join(xdg_cache_home(), _APP_NAMESPACE, *subpaths)

def app_data_dir(*subpaths: str) -> str:
    """App-namespaced data dir: ``<xdg_data_home>/mindor/<subpaths>``."""
    return os.path.join(xdg_data_home(), _APP_NAMESPACE, *subpaths)
