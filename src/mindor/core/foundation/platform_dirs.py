import os

_APP_NAMESPACE = "mindor"

def app_cache_dir(*subpaths: str) -> str:
    """App-namespaced cache dir. POSIX: ``$XDG_CACHE_HOME/mindor/<subpaths>``
    or ``~/.cache/mindor/<subpaths>`` — the root HuggingFace / PyTorch /
    Ollama default to, so AI-tool caches share one tree. Windows:
    ``%LOCALAPPDATA%\\mindor\\Cache\\<subpaths>`` — Windows has no
    conventional cache-only root, and pip/pipx/uv also co-locate cache
    under ``LocalAppData``; the extra ``Cache`` segment separates it from
    the data dir which lands in the same tree. Override order (both
    platforms): ``$MINDOR_CACHE_HOME`` wins first, then ``$XDG_CACHE_HOME``
    — the former is native to Windows users who do not know XDG, the
    latter stays supported so Unix / WSL users can point every AI tool at
    the same root with one env var."""
    base_dir = os.environ.get("MINDOR_CACHE_HOME") or os.environ.get("XDG_CACHE_HOME")

    if base_dir is None:
        if os.name == "nt":
            local_app_data = os.environ.get("LOCALAPPDATA") or os.path.expanduser(r"~\AppData\Local")
            base_dir = os.path.join(local_app_data, _APP_NAMESPACE, "Cache")
        else:
            base_dir = os.path.join(os.path.expanduser("~/.cache"), _APP_NAMESPACE)
    else:
        base_dir = os.path.join(base_dir, _APP_NAMESPACE)

    return os.path.join(base_dir, *subpaths)

def app_data_dir(*subpaths: str) -> str:
    """App-namespaced data dir for persistent artifacts whose loss hurts
    (venvs, pod state, ...). POSIX: ``$XDG_DATA_HOME/mindor/<subpaths>``
    or ``~/.local/share/mindor/<subpaths>``. Windows:
    ``%LOCALAPPDATA%\\mindor\\<subpaths>`` — uv's tool directory uses the
    same location, and there is no roaming/local split that makes sense
    here. Override order (both platforms): ``$MINDOR_DATA_HOME`` wins
    first, then ``$XDG_DATA_HOME`` — point either at a non-system drive
    to keep ``venvs/`` off a small C: SSD."""
    base_dir = os.environ.get("MINDOR_DATA_HOME") or os.environ.get("XDG_DATA_HOME")

    if base_dir is None:
        if os.name == "nt":
            base_dir = os.environ.get("LOCALAPPDATA") or os.path.expanduser(r"~\AppData\Local")
        else:
            base_dir = os.path.expanduser("~/.local/share")

    return os.path.join(base_dir, _APP_NAMESPACE, *subpaths)
