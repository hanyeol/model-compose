import importlib.metadata

def _resolve_version() -> str:
    try:
        root_package = __package__.split(".")[0]
        distribution_name = importlib.metadata.packages_distributions()[root_package][0]
        return importlib.metadata.version(distribution_name)
    except (KeyError, importlib.metadata.PackageNotFoundError):
        return "latest"

__version__ = _resolve_version()
