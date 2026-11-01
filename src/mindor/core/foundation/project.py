from pathlib import Path
import hashlib

def get_component_state_path(component_id: str) -> Path:
    """Absolute path to a component's per-project persistent state directory
    under ``~/.mindor/projects/<ns>/components/<component_id>/``. Returned
    without being created — callers mkdir when they first write."""
    return Path.home() / ".mindor" / "projects" / get_project_namespace() / "components" / component_id

def get_project_namespace() -> str:
    """Short stable hash of the current compose project's working directory.
    Namespaces persistent per-project state (pod auth tokens, caches, ...)
    on the host so parallel compose projects do not collide. Resolves cwd
    first so symlinks / `.`-relative segments map to the same bucket."""
    return hashlib.sha256(str(Path.cwd().resolve()).encode("utf-8")).hexdigest()[:16]
