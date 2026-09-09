from typing import BinaryIO, Optional
from pathlib import Path
import tarfile

def extract_tarball(stream: BinaryIO, dest_dir: Path, strip_top_level: bool = False) -> None:
    """Stream-extract a gzipped tarball from a file-like object into `dest_dir`.

    When `strip_top_level` is True, the archive's single top-level directory is
    stripped from every member path so the tree contents are laid out directly
    under `dest_dir`. This matches the shape of GitHub codeload tarballs, which
    wrap the tree in a `<repo>-<sha>/` prefix.
    """
    # `r|gz` reads the archive as a stream (single pass, no seeking). This lets
    # callers pass an HTTP response directly, without buffering the whole
    # archive into memory first.
    with tarfile.open(fileobj=stream, mode="r|gz") as archive:
        dest_dir.mkdir(parents=True, exist_ok=True)

        top_level: Optional[str] = None

        for member in archive:
            if strip_top_level:
                head, _, tail = member.name.partition("/")

                if top_level is None:
                    top_level = head

                if head != top_level:
                    raise ValueError(f"Archive has multiple top-level entries: '{top_level}', '{head}'")

                if not tail:
                    continue

                member.name = tail

            archive.extract(member, dest_dir)
