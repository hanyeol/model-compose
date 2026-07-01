from .specs import ControllerRuntimeSpecs
from pathlib import Path
import shutil, yaml

def generate_workspace_bundle(specs: ControllerRuntimeSpecs, target: Path) -> None:
    """Write the workspace bundle the in-container `bootstrap.sh` expects
    at `/mnt/bootstrap`. Always rebuilt from scratch — old contents are
    wiped first so stale files cannot leak between launches.

    Layout produced:
        <target>/model-compose.yml    (transformed specs)
        <target>/webui/server/        (if configured + exists on host)
        <target>/webui/static/        (if configured + exists on host)
    """
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)

    with (target / "model-compose.yml").open("w") as f:
        yaml.dump(specs.generate_native_runtime_specs(), f, sort_keys=False)

    server_dir = getattr(specs.controller.webui, "server_dir", None)
    if server_dir:
        source = (Path.cwd() / server_dir).resolve()
        if source.is_dir():
            shutil.copytree(
                source,
                target / "webui" / "server",
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
            )

    static_dir = getattr(specs.controller.webui, "static_dir", None)
    if static_dir:
        source = (Path.cwd() / static_dir).resolve()
        if source.is_dir():
            shutil.copytree(
                source,
                target / "webui" / "static",
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
            )
