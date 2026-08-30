from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, List, Any
from mindor.core.logger import logging
from .ssh_client import SshClient
import asyncio, stat as stat_module, posixpath

if TYPE_CHECKING:
    import paramiko

class SftpClient(SshClient):
    """SSH client that additionally opens an SFTP subsystem alongside the transport.

    The API mirrors paramiko's SFTPClient but wraps every blocking call in
    ``asyncio.to_thread`` so callers stay on the event loop. Returned handles
    (``SFTPFile``, ``SFTPAttributes``) are paramiko types — higher-level
    streaming adapters are the caller's responsibility.
    """
    def __init__(self, params):
        super().__init__(params)

        self.sftp: Optional[paramiko.SFTPClient] = None

    async def connect(self) -> None:
        await super().connect()

        def _open() -> paramiko.SFTPClient:
            sftp = self.client.open_sftp()

            logging.debug(f"SFTP session opened to {self.params.host}:{self.params.port}")

            return sftp

        self.sftp = await asyncio.to_thread(_open)

    async def close(self) -> None:
        def _close():
            try:
                self.sftp.close()
                logging.debug(f"SFTP session closed to {self.params.host}:{self.params.port}")
            except Exception as e:
                logging.warning(f"Error closing SFTP session: {e}")

        if self.sftp is not None:
            await asyncio.to_thread(_close)

        self.sftp = None

        await super().close()

    async def open_file(self, path: str, mode: str = "r", bufsize: int = -1) -> paramiko.SFTPFile:
        return await asyncio.to_thread(self.sftp.open, path, mode, bufsize)

    async def remove_file(self, path: str) -> None:
        await asyncio.to_thread(self.sftp.remove, path)

    async def create_directory(self, path: str, mode: int = 0o777, exist_ok: bool = False, parents: bool = False) -> None:
        """Create ``path`` (analogous to ``os.makedirs`` when ``parents=True``)."""
        def _create_directory() -> None:
            if parents:
                paths_to_create: List[str] = []
                current_dir = path.rstrip("/")

                while current_dir and current_dir != "/":
                    try:
                        attrs = self.sftp.stat(current_dir)
                        if not stat_module.S_ISDIR(attrs.st_mode):
                            raise NotADirectoryError(f"Path exists and is not a directory: {current_dir}")
                        if not exist_ok and not paths_to_create:
                            raise FileExistsError(f"Directory already exists: {current_dir}")
                        break
                    except FileNotFoundError:
                        paths_to_create.append(current_dir)
                        current_dir = posixpath.dirname(current_dir)

                for directory in reversed(paths_to_create):
                    try:
                        self.sftp.mkdir(directory, mode)
                    except OSError:
                        # Another actor may have created it between stat and mkdir.
                        try:
                            attrs = self.sftp.stat(directory)
                            if not stat_module.S_ISDIR(attrs.st_mode):
                                raise
                        except FileNotFoundError:
                            raise
            else:
                try:
                    self.sftp.mkdir(path, mode)
                except OSError:
                    if not exist_ok:
                        raise
                    try:
                        attrs = self.sftp.stat(path)
                        if not stat_module.S_ISDIR(attrs.st_mode):
                            raise
                    except FileNotFoundError:
                        raise

        await asyncio.to_thread(_create_directory)

    async def remove_directory(self, path: str) -> None:
        await asyncio.to_thread(self.sftp.rmdir, path)

    async def list_directory(self, path: str) -> List[paramiko.SFTPAttributes]:
        return await asyncio.to_thread(self.sftp.listdir_attr, path)

    async def rename(self, src: str, dst: str) -> None:
        """Rename ``src`` to ``dst``. Uses ``posix_rename`` when the server supports it (atomic overwrite)."""
        def _rename() -> None:
            posix_rename = getattr(self.sftp, "posix_rename", None)
            if posix_rename is not None:
                try:
                    posix_rename(src, dst)
                    return
                except (IOError, OSError):
                    pass
            self.sftp.rename(src, dst)

        await asyncio.to_thread(_rename)

    async def exists(self, path: str) -> bool:
        def _exists() -> bool:
            try:
                self.sftp.stat(path)
                return True
            except FileNotFoundError:
                return False
            except IOError:
                return False

        return await asyncio.to_thread(_exists)

    async def stat(self, path: str) -> paramiko.SFTPAttributes:
        return await asyncio.to_thread(self.sftp.stat, path)

    async def is_directory(self, path: str) -> bool:
        def _is_directory() -> bool:
            try:
                return stat_module.S_ISDIR(self.sftp.stat(path).st_mode)
            except FileNotFoundError:
                return False

        return await asyncio.to_thread(_is_directory)

    async def is_file(self, path: str) -> bool:
        def _is_file() -> bool:
            try:
                return stat_module.S_ISREG(self.sftp.stat(path).st_mode)
            except FileNotFoundError:
                return False

        return await asyncio.to_thread(_is_file)
