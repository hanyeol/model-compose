from abc import ABC
from mindor.dsl.schema.runtime import CommonRuntimeConfig
from mindor.core.foundation.package import mindor as mindor_package

class CommonRuntime(ABC):
    """Marker base for isolated runtime lifecycle wrappers.

    A ``*Runtime`` owns one isolated unit of execution (venv, container, remote
    pod, process) and exposes a lifecycle for its parent manager to drive —
    knows nothing about IPC protocols, codecs, or channels. Subclasses supply
    their own lifecycle verbs (bootstrap/create, start, stop, remove, ...) —
    the exact set depends on the isolation mechanism."""
    def __init__(self, config: CommonRuntimeConfig, verbose: bool = False):
        self.config: CommonRuntimeConfig = config
        self.verbose: bool = verbose

    @staticmethod
    def _is_editable_install() -> bool:
        """Return True when the host `mindor` package is a pip editable install
        (PEP 660 `__editable__.mindor-*.pth` or legacy `mindor.egg-link`), or a
        source checkout without pip metadata (`pyproject.toml` sitting next to
        the source tree). Isolated runtimes use this to decide whether to
        re-ship the host source on every launch (editable → always) or cache
        it by version (released → copy once)."""
        mindor_root_path = mindor_package.get_root_path()
        host_site_packages = mindor_root_path.parent

        if any(host_site_packages.glob("__editable__.mindor-*.pth")):
            return True

        if (host_site_packages / "mindor.egg-link").exists():
            return True

        if (mindor_root_path.parent.parent / "pyproject.toml").exists():
            return True

        return False
