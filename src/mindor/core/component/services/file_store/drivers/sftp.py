from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import SftpFileStoreComponentConfig
from mindor.dsl.schema.action import FileStoreActionConfig, SftpFileStoreActionConfig
from mindor.dsl.schema.transport.ssh import SshAuthType, SshConnectionConfig
from mindor.core.foundation.streaming.resources import ReaderStreamResource, ChunkedStreamResource, save_stream_to_file
from mindor.core.foundation.streaming.resolver import resolve_stream_resource
from mindor.core.foundation.variable.time import parse_time
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.files import is_glob_match, is_posix_path_within, guess_content_type
from mindor.core.utils.time import format_datetime_iso_string
from mindor.core.utils.transport.sftp_client import SftpClient
from mindor.core.utils.transport.ssh_client import (
    SshAuthParams,
    SshConnectionParams,
    SshKeyfileAuthParams,
    SshPasswordAuthParams,
)
from ..base import FileStoreService, FileStoreDriver, register_file_store_service
from ..base import ComponentActionContext
from .common import FileStoreAction
import asyncio, os, sys
import stat as stat_module
import posixpath, urllib.parse

if TYPE_CHECKING:
    import paramiko

_DEFAULT_CHUNK_SIZE = 8 * 1024 * 1024  # 8MB — for put and save_to downloads
_DEFAULT_STREAMING_CHUNK_SIZE = 8 * 1024  # 8KB — for streaming output, matching other StreamResources

class SftpFileReader:
    """Adapts a paramiko ``SFTPFile`` to the ``BytesReader`` protocol with executor-offloaded IO."""
    def __init__(self, handle: paramiko.SFTPFile):
        self.handle: paramiko.SFTPFile = handle

    async def read(self, size: int) -> bytes:
        return await asyncio.to_thread(self.handle.read, size)

    async def close(self) -> None:
        await asyncio.to_thread(self.handle.close)

class SftpFileStoreAction(FileStoreAction):
    def __init__(
        self,
        config: SftpFileStoreActionConfig,
        client: SftpClient,
        base_path: str,
    ):
        super().__init__(config)

        self.client: SftpClient = client
        self.base_path: str = base_path  # posix, normalized, no trailing slash except for root

    async def _put(
        self,
        path: Any,
        source: Any,
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> Dict[str, Any]:
        content_type = params["content_type"]
        chunk_size   = params["chunk_size"] or _DEFAULT_CHUNK_SIZE

        source = await resolve_stream_resource(source) if source is not None else None

        if source is None:
            raise ValueError("'source' is required for 'put' action")

        remote_path = self._resolve_remote_path(path)
        content_type = content_type or guess_content_type(path) or source.content_type

        parent = posixpath.dirname(remote_path)

        if parent and parent != "/":
            await self.client.create_directory(parent, exist_ok=True, parents=True)

        tmp_path = f"{remote_path}.tmp"

        try:
            uploaded_size = await self._upload_stream(source, tmp_path, chunk_size)
            await self.client.rename(tmp_path, remote_path)
        except BaseException:
            try:
                await self.client.remove_file(tmp_path)
            except Exception:
                pass
            raise

        return {
            "path": path,
            "url": self._build_file_url(remote_path),
            "size": uploaded_size,
            "content_type": content_type,
        }

    async def _get(
        self,
        path: Any,
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> Dict[str, Any]:
        save_to    = params["save_to"]
        streaming  = params["streaming"]
        chunk_size = params["chunk_size"]

        remote_path = self._resolve_remote_path(path)

        try:
            attrs = await self.client.stat(remote_path)
        except FileNotFoundError:
            raise FileNotFoundError(f"File not found: {path!r}")

        if not stat_module.S_ISREG(attrs.st_mode):
            raise IsADirectoryError(f"Path is not a file: {path!r}")

        url = self._build_file_url(remote_path)
        content_type = guess_content_type(path)
        modified_at = format_datetime_iso_string(attrs.st_mtime) if attrs.st_mtime is not None else None

        if save_to:
            if os.path.isdir(save_to):
                save_to = os.path.join(save_to, posixpath.basename(path))

            parent = os.path.dirname(os.path.abspath(save_to))

            if parent:
                os.makedirs(parent, exist_ok=True)

            file = await self.client.open_file(remote_path, "rb")
            stream = ReaderStreamResource(
                SftpFileReader(file),
                chunk_size=chunk_size or _DEFAULT_CHUNK_SIZE,
                size=attrs.st_size,
            )
            await save_stream_to_file(stream, save_to)

            return {
                "path": path,
                "url": url,
                "size": attrs.st_size,
                "content_type": content_type,
                "modified_at": modified_at,
                "save_to": save_to,
            }

        if streaming:
            file = await self.client.open_file(remote_path, "rb")
            content = ReaderStreamResource(
                SftpFileReader(file),
                content_type=content_type,
                filename=posixpath.basename(path) or None,
                chunk_size=chunk_size or _DEFAULT_STREAMING_CHUNK_SIZE,
                size=attrs.st_size,
            )

            return {
                "path": path,
                "url": url,
                "size": attrs.st_size,
                "content_type": content_type,
                "modified_at": modified_at,
                "content": content,
            }

        file = await self.client.open_file(remote_path, "rb")

        try:
            content = await asyncio.to_thread(file.read)
        finally:
            await asyncio.to_thread(file.close)

        return {
            "path": path,
            "url": url,
            "size": attrs.st_size,
            "content_type": content_type,
            "modified_at": modified_at,
            "content": content,
        }

    async def _delete(
        self,
        path: Any,
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> Dict[str, Any]:
        remote_path = self._resolve_remote_path(path)

        try:
            await self.client.remove_file(remote_path)
        except FileNotFoundError:
            pass

        return { "path": path }

    async def _exists(
        self,
        path: Any,
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> Dict[str, Any]:
        remote_path = self._resolve_remote_path(path)
        exists = await self.client.exists(remote_path)

        return { "path": path, "exists": exists }

    async def _list(
        self,
        path: Any,
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> Dict[str, Any]:
        recursive        = params["recursive"]
        pattern          = params["pattern"]
        max_result_count = params["max_result_count"]
        page_token       = params["next_token"]

        list_path = self._resolve_remote_path(path) if path else self.base_path

        if not await self.client.is_directory(list_path):
            raise NotADirectoryError(f"Path is not a directory: {path!r}")

        start_index = int(page_token) if page_token else 0
        limit = int(max_result_count) if max_result_count is not None else sys.maxsize

        items: List[Dict[str, Any]] = []
        offset = 0

        async for dir_path, entries in self._iterate_files(list_path, recursive):
            for entry in entries:
                if not stat_module.S_ISREG(entry.st_mode):
                    continue

                absolute_path = posixpath.join(dir_path, entry.filename)
                relative_path = self._resolve_relative_path(absolute_path)

                if pattern and not is_glob_match(relative_path, pattern):
                    continue

                if offset >= start_index:
                    items.append({
                        "path": relative_path,
                        "url": self._build_file_url(absolute_path),
                        "size": entry.st_size,
                        "content_type": guess_content_type(relative_path),
                        "modified_at": format_datetime_iso_string(entry.st_mtime) if entry.st_mtime is not None else None,
                    })

                    if len(items) >= limit:
                        return {
                            "items": items,
                            "count": len(items),
                            "next_token": str(offset + 1),
                        }

                offset += 1

        return {
            "items": items,
            "count": len(items),
            "next_token": None,
        }

    async def _iterate_files(
        self,
        list_path: str,
        recursive: bool,
    ) -> AsyncIterator[tuple]:
        entries = await self.client.list_directory(list_path)

        if not recursive:
            yield list_path, entries
            return

        yield list_path, entries

        for entry in entries:
            if stat_module.S_ISDIR(entry.st_mode):
                child_path = posixpath.join(list_path, entry.filename)
                async for child_dir, child_entries in self._iterate_files(child_path, recursive):
                    yield child_dir, child_entries

    async def _upload_stream(self, source: Any, remote_path: str, chunk_size: int) -> int:
        file = await self.client.open_file(remote_path, "wb")
        uploaded_size = 0

        try:
            async with ChunkedStreamResource(source, chunk_size) as stream:
                async for chunk in stream:
                    await asyncio.to_thread(file.write, chunk)
                    uploaded_size += len(chunk)
        finally:
            await asyncio.to_thread(file.close)

        return uploaded_size

    def _resolve_remote_path(self, path: str) -> str:
        remote_path = posixpath.normpath(posixpath.join(self.base_path, path.lstrip("/")))

        if not is_posix_path_within(self.base_path, remote_path):
            raise PermissionError(f"Path escapes the allowed root directory: {path!r}")

        return remote_path

    def _resolve_relative_path(self, absolute_path: str) -> str:
        relative_path = posixpath.relpath(absolute_path, self.base_path)

        if relative_path == ".":
            return ""

        return relative_path

    def _build_file_url(self, absolute_path: str) -> str:
        host = self.client.params.host
        port = self.client.params.port

        username = urllib.parse.quote(self.client.params.auth.username, safe="")
        path = urllib.parse.quote(absolute_path, safe="/")
        port = f":{port}" if port and port != 22 else ""

        return f"sftp://{username}@{host}{port}{path}"

@register_file_store_service(FileStoreDriver.SFTP)
class SftpFileStoreService(FileStoreService):
    config: SftpFileStoreComponentConfig

    def __init__(self, id: str, config: SftpFileStoreComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.base_path: str = self._normalize_posix_base_path(config.base_path)
        self.client: Optional[SftpClient] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "paramiko" ]

    async def _start(self) -> None:
        self.client = self._create_client()
        await self.client.connect()

        await super()._start()

    async def _stop(self) -> None:
        await super()._stop()

        if self.client is not None:
            try:
                await self.client.close()
            finally:
                self.client = None

    async def _run(self, action: FileStoreActionConfig, context: ComponentActionContext) -> Any:
        return await SftpFileStoreAction(action, self.client, self.base_path).run(context)

    def _create_client(self) -> SftpClient:
        return SftpClient(self._build_connection_params(self.config.connection))

    def _build_connection_params(self, config: SshConnectionConfig) -> SshConnectionParams:
        return SshConnectionParams(
            host=config.host,
            port=config.port,
            auth=self._build_auth_params(config.auth),
            keepalive_interval=int(parse_time(config.keepalive_interval)),
        )

    def _build_auth_params(self, config) -> SshAuthParams:
        if config.type == SshAuthType.KEYFILE:
            return SshKeyfileAuthParams(
                username=config.username,
                keyfile=config.keyfile,
                passphrase=config.passphrase,
            )

        if config.type == SshAuthType.PASSWORD:
            return SshPasswordAuthParams(
                username=config.username,
                password=config.password,
            )

        raise ValueError(f"Unknown SSH auth type: {config.type}")

    def _normalize_posix_base_path(self, base_path: Optional[str]) -> str:
        if not base_path:
            return "/"

        normalized = posixpath.normpath(base_path)
        if not normalized.startswith("/"):
            normalized = "/" + normalized

        return normalized
