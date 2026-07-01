from typing import Callable, Dict, Iterator, Optional, Union
from contextlib import contextmanager
from pathlib import Path
import io, shutil, tarfile, tempfile

TarFilter = Callable[[tarfile.TarInfo], Optional[tarfile.TarInfo]]

# Archives under this size live entirely in RAM; larger ones spill to disk
# via tempfile so we never hold a multi-MB tarball in memory just to hand
# it to docker.
_DEFAULT_SPOOL_MAX = 4 * 1024 * 1024  # 4 MiB

def archive_to_tar(
    files: Optional[Dict[str, Union[Path, bytes, bytearray]]] = None,
    dirs: Optional[Dict[str, Path]] = None,
    filter: Optional[TarFilter] = None,
    spool_max_size: int = _DEFAULT_SPOOL_MAX,
) -> tempfile.SpooledTemporaryFile:
    """Build an uncompressed tar archive into a spooled temp file.

    The returned object is a `tempfile.SpooledTemporaryFile` (file-like)
    positioned at offset 0 and ready to be passed to `docker.api.build(
    fileobj=...)` or `container.put_archive(...)`. Archives smaller than
    `spool_max_size` stay entirely in memory; larger ones spill to disk
    transparently — callers do not have to know which.

    Callers are responsible for closing the returned file (use `with`).

    - `files`: single-file entries. Value can be:
        - `bytes` — written verbatim with mode 0o644.
        - `Path` — read from disk; stat metadata (mode, mtime) is preserved.
          Must point to a regular file; use `dirs` for directory trees.
    - `dirs`: host-side directories to recurse into (dict key = arcname root).
    - `filter`: optional `tarfile.add(filter=...)` predicate applied to
      `Path`-valued file entries and to directory entries.
    """
    tar_file = tempfile.SpooledTemporaryFile(max_size=spool_max_size, mode="w+b")
    try:
        with tarfile.open(fileobj=tar_file, mode="w") as tar:
            for arcname, source in (files or {}).items():
                if isinstance(source, (bytes, bytearray)):
                    info = tarfile.TarInfo(name=arcname)
                    info.size = len(source)
                    info.mode = 0o644
                    tar.addfile(info, io.BytesIO(bytes(source)))
                elif isinstance(source, Path):
                    if not source.is_file():
                        raise ValueError(
                            f"files[{arcname!r}] must be a regular file Path; "
                            f"use `dirs` for directory trees"
                        )
                    tar.add(str(source), arcname=arcname, recursive=False, filter=filter)
                else:
                    raise TypeError(
                        f"files[{arcname!r}] must be bytes or Path, got {type(source).__name__}"
                    )
            for arcname, src in (dirs or {}).items():
                tar.add(str(src), arcname=arcname, recursive=True, filter=filter)
    except Exception:
        tar_file.close()
        raise

    tar_file.seek(0)

    return tar_file

@contextmanager
def archive_to_dir(
    files: Optional[Dict[str, Union[Path, bytes, bytearray]]] = None,
    dirs: Optional[Dict[str, Path]] = None,
    filter: Optional[TarFilter] = None,
    root: Optional[Path] = None,
) -> Iterator[Path]:
    """Materialize `files` / `dirs` into a real directory on disk and yield
    its path. Cleaned up on context exit.

    Mirrors `archive_to_tar` for clients that need a directory rather than
    a tar stream. Reuses `archive_to_tar` so layout/filter semantics stay
    identical.

    `root` selects the parent directory under which the temporary directory
    is created; defaults to the system temp dir.
    """
    if root is not None:
        root.mkdir(parents=True, exist_ok=True)
    target_dir = Path(tempfile.mkdtemp(dir=str(root) if root else None))
    try:
        with archive_to_tar(files=files, dirs=dirs, filter=filter) as tar_file:
            with tarfile.open(fileobj=tar_file, mode="r") as tar:
                tar.extractall(path=str(target_dir))
        yield target_dir
    finally:
        shutil.rmtree(target_dir, ignore_errors=True)

def skip_python_artifacts(info: tarfile.TarInfo) -> Optional[tarfile.TarInfo]:
    """A `TarFilter` that drops Python build artifacts (`__pycache__`
    directories and `*.pyc` files).

    Pass to `archive_to_tar(..., filter=skip_python_artifacts)` when packing
    a Python source tree for image build / workspace injection — Python
    re-creates these on import, so shipping the host's copy only bloats the
    archive and risks Python-version skew.
    """
    basename = Path(info.name).name
    if basename == "__pycache__" or basename.endswith(".pyc"):
        return None
    return info
