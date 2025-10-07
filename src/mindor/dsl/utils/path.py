import os

# Platform-specific relative path prefixes
RELATIVE_PATH_PREFIXES = (
    f".{os.sep}",   # Current directory (e.g., ./ or .\)
    f"..{os.sep}",  # Parent directory (e.g., ../ or ..\)
    f"~{os.sep}",   # Home directory (e.g., ~/ or ~\)
)

def is_local_path(path: str) -> bool:
    # Check for explicit relative path prefixes (platform-independent)
    if path.startswith(RELATIVE_PATH_PREFIXES):
        return True

    # Check for absolute path for Unix-style
    if path.startswith("/"):
        return True

    # Check for Windows-style drive paths (C:\, D:\, etc.)
    if len(path) >= 3 and path[1] == ":" and path[2] in ("\\", "/"):
        return True

    return False
