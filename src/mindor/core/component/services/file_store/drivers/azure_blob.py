from __future__ import annotations
from typing import TYPE_CHECKING

from dataclasses import dataclass
from typing import Optional, Dict, List, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import AzureBlobFileStoreComponentConfig
from mindor.dsl.schema.action import FileStoreActionConfig, AzureBlobFileStoreActionConfig
from mindor.core.foundation.streaming.resources import save_stream_to_file
from mindor.core.foundation.streaming.resolver import resolve_stream_resource
from mindor.core.utils.files import is_glob_match, guess_content_type
from mindor.core.utils.time import format_datetime_iso_string
from mindor.core.foundation.providers.azure_blob import upload, multipart_upload
from ..base import FileStoreService, FileStoreDriver, register_file_store_service
from ..base import ComponentActionContext
from .common import FileStoreAction
import os, urllib.parse

if TYPE_CHECKING:
    from azure.storage.blob.aio import BlobServiceClient, ContainerClient, BlobClient, StorageStreamDownloader

_DEFAULT_CHUNK_SIZE = 8 * 1024 * 1024  # 8MB — for put and save_to downloads
_DEFAULT_STREAMING_CHUNK_SIZE = 8 * 1024  # 8KB — for streaming output, matching other StreamResources
_DEFAULT_MULTIPART_THRESHOLD = 8 * 1024 * 1024  # 8MB

@dataclass(frozen=True)
class AzureBlobLocation:
    container: str
    account_name: Optional[str] = None

class AzureBlobDownloadReader:
    """Adapts an Azure StorageStreamDownloader to the .read(size) -> bytes interface
    expected by ReaderStreamResource."""
    def __init__(self, downloader: StorageStreamDownloader, chunk_size: int):
        self._chunks: Optional[AsyncIterator[bytes]] = downloader.chunks()
        self._buffer = bytearray()
        self._exhausted = False
        self._chunk_size = chunk_size

    async def read(self, size: int = -1) -> bytes:
        if self._exhausted and not self._buffer:
            return b""

        if size is None or size < 0:
            while not self._exhausted:
                await self._pull_next()
            data = bytes(self._buffer)
            self._buffer.clear()
            return data

        while len(self._buffer) < size and not self._exhausted:
            await self._pull_next()

        if not self._buffer:
            return b""

        data = bytes(self._buffer[:size])
        del self._buffer[:size]
        return data

    async def close(self) -> None:
        self._chunks = None
        self._exhausted = True
        self._buffer.clear()

    async def _pull_next(self) -> None:
        try:
            chunk = await self._chunks.__anext__()
            self._buffer.extend(chunk)
        except StopAsyncIteration:
            self._exhausted = True

class AzureBlobFileStoreAction(FileStoreAction):
    def __init__(
        self,
        config: AzureBlobFileStoreActionConfig,
        container_client: ContainerClient,
        location: AzureBlobLocation,
        base_path: Optional[str] = None,
    ):
        super().__init__(config)

        self.container_client: ContainerClient = container_client
        self.location: AzureBlobLocation = location
        self.base_path: Optional[str] = base_path

    async def _put(self, context: ComponentActionContext) -> Dict[str, Any]:
        path                = await context.render_variable(self.config.path)
        source              = await context.render_variable(self.config.source)
        content_type        = await context.render_variable(self.config.content_type)
        metadata            = await context.render_variable(self.config.metadata)
        multipart_threshold = await context.render_size(self.config.multipart_threshold, _DEFAULT_MULTIPART_THRESHOLD)
        chunk_size          = await context.render_size(self.config.chunk_size, _DEFAULT_CHUNK_SIZE)

        source = await resolve_stream_resource(source) if source is not None else None

        if source is None:
            raise ValueError("'source' is required for 'put' action")

        blob_name     = self._resolve_blob_name(path)
        content_type  = content_type or guess_content_type(path) or source.content_type
        use_multipart = source.size is None or source.size > multipart_threshold

        blob_client = self.container_client.get_blob_client(blob_name)

        if use_multipart:
            uploaded_size = await multipart_upload(
                blob_client,
                source,
                chunk_size=chunk_size,
                content_type=content_type,
                metadata=metadata,
            )
        else:
            uploaded_size = await upload(
                blob_client,
                source,
                content_type=content_type,
                metadata=metadata,
            )

        return {
            "path": path,
            "url": self._build_file_url(blob_name),
            "size": uploaded_size,
            "content_type": content_type,
        }

    async def _get(self, context: ComponentActionContext) -> Dict[str, Any]:
        from mindor.core.foundation.streaming.resources import ReaderStreamResource

        path       = await context.render_variable(self.config.path)
        save_to    = await context.render_variable(self.config.save_to)
        streaming  = await context.render_variable(self.config.streaming)
        chunk_size = await context.render_size(self.config.chunk_size)

        blob_name = self._resolve_blob_name(path)
        blob_client = self.container_client.get_blob_client(blob_name)

        downloader = await blob_client.download_blob()
        properties = downloader.properties

        size = properties.size
        content_type = getattr(properties.content_settings, "content_type", None) or guess_content_type(path)
        last_modified = properties.last_modified
        modified_at = format_datetime_iso_string(last_modified) if last_modified else None
        url = self._build_file_url(blob_name)

        if save_to:
            if os.path.isdir(save_to):
                save_to = os.path.join(save_to, os.path.basename(path))

            parent = os.path.dirname(os.path.abspath(save_to))
            if parent:
                os.makedirs(parent, exist_ok=True)

            reader = AzureBlobDownloadReader(downloader, chunk_size or _DEFAULT_CHUNK_SIZE)
            stream = ReaderStreamResource(reader, chunk_size=chunk_size or _DEFAULT_CHUNK_SIZE)
            await save_stream_to_file(stream, save_to)

            return {
                "path": path,
                "url": url,
                "size": size if size is not None else os.path.getsize(save_to),
                "content_type": content_type,
                "modified_at": modified_at,
                "save_to": save_to,
            }

        if streaming:
            reader = AzureBlobDownloadReader(downloader, chunk_size or _DEFAULT_STREAMING_CHUNK_SIZE)
            content = ReaderStreamResource(
                reader,
                content_type=content_type,
                filename=os.path.basename(path) or None,
                chunk_size=chunk_size or _DEFAULT_STREAMING_CHUNK_SIZE,
            )

            return {
                "path": path,
                "url": url,
                "size": size,
                "content_type": content_type,
                "modified_at": modified_at,
                "content": content,
            }

        content = await downloader.readall()

        return {
            "path": path,
            "url": url,
            "size": size if size is not None else len(content),
            "content_type": content_type,
            "modified_at": modified_at,
            "content": content,
        }

    async def _delete(self, context: ComponentActionContext) -> Dict[str, Any]:
        path = await context.render_variable(self.config.path)

        blob_name = self._resolve_blob_name(path)

        await self.container_client.delete_blob(blob_name)

        return { "path": path }

    async def _exists(self, context: ComponentActionContext) -> Dict[str, Any]:
        path = await context.render_variable(self.config.path)

        blob_name = self._resolve_blob_name(path)
        blob_client = self.container_client.get_blob_client(blob_name)

        exists = await blob_client.exists()

        return { "path": path, "exists": exists }

    async def _list(self, context: ComponentActionContext) -> Dict[str, Any]:
        path             = await context.render_variable(self.config.path)
        recursive        = await context.render_variable(self.config.recursive)
        pattern          = await context.render_variable(self.config.pattern)
        max_result_count = await context.render_variable(self.config.max_result_count)
        next_token       = await context.render_variable(self.config.next_token)

        name_prefix = self._resolve_blob_name(path) if path else (self.base_path or "")

        list_params: Dict[str, Any] = {}
        if name_prefix:
            list_params["name_starts_with"] = name_prefix
        if max_result_count is not None:
            list_params["results_per_page"] = int(max_result_count)

        if recursive:
            blobs = self.container_client.list_blobs(**list_params)
        else:
            # Azure exposes hierarchical listing through `walk_blobs`; "/" is the
            # default delimiter and matches the S3 driver's behavior.
            blobs = self.container_client.walk_blobs(delimiter="/", **list_params)

        pages = blobs.by_page(continuation_token=next_token or None)

        items: List[Dict[str, Any]] = []
        continuation: Optional[str] = None

        try:
            page = await pages.__anext__()
        except StopAsyncIteration:
            page = None

        if page is not None:
            from azure.storage.blob import BlobPrefix as SyncBlobPrefix
            from azure.storage.blob.aio import BlobPrefix as AsyncBlobPrefix
            prefix_classes = (SyncBlobPrefix, AsyncBlobPrefix)

            async for blob in page:
                # `walk_blobs` yields BlobPrefix entries for "subdirectories";
                # skip them to match the S3 driver, which only reports object keys.
                # The sync and aio SDKs each ship their own BlobPrefix class.
                if isinstance(blob, prefix_classes):
                    continue

                relative_path = self._resolve_relative_path(blob.name)
                last_modified = blob.last_modified
                content_type = getattr(blob.content_settings, "content_type", None) or guess_content_type(relative_path)

                if pattern and not is_glob_match(relative_path, pattern):
                    continue

                items.append({
                    "path": relative_path,
                    "url": self._build_file_url(blob.name),
                    "size": blob.size,
                    "content_type": content_type,
                    "modified_at": format_datetime_iso_string(last_modified) if last_modified else None,
                })

            continuation = pages.continuation_token

        return {
            "items": items,
            "count": len(items),
            "next_token": continuation or None,
        }

    def _resolve_blob_name(self, path: str) -> str:
        if self.base_path:
            return f"{self.base_path}{path.lstrip('/')}"

        return path

    def _resolve_relative_path(self, blob_name: str) -> str:
        if self.base_path and blob_name.startswith(self.base_path):
            return blob_name[len(self.base_path):]

        return blob_name

    def _build_file_url(self, blob_name: str) -> str:
        quoted_blob_name = urllib.parse.quote(blob_name, safe="/")

        if self.location.account_name:
            return f"https://{self.location.account_name}.blob.core.windows.net/{self.location.container}/{quoted_blob_name}"

        return f"{self.location.container}/{quoted_blob_name}"

@register_file_store_service(FileStoreDriver.AZURE_BLOB)
class AzureBlobFileStoreService(FileStoreService):
    config: AzureBlobFileStoreComponentConfig

    def __init__(self, id: str, config: AzureBlobFileStoreComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.location: AzureBlobLocation = AzureBlobLocation(
            container=config.container,
            account_name=config.account_name,
        )
        self.base_path: Optional[str] = (config.base_path.rstrip("/") + "/") if config.base_path else None
        self.service_client: Optional[BlobServiceClient] = None
        self.container_client: Optional[ContainerClient] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "azure-storage-blob", "aiohttp" ]

    async def _start(self) -> None:
        self.service_client = self._create_service_client()
        self.container_client = self.service_client.get_container_client(self.config.container)
        await super()._start()

    async def _stop(self) -> None:
        await super()._stop()
        if self.container_client is not None:
            try:
                await self.container_client.close()
            finally:
                self.container_client = None
        if self.service_client is not None:
            try:
                await self.service_client.close()
            finally:
                self.service_client = None

    async def _run(self, action: FileStoreActionConfig, context: ComponentActionContext) -> Any:
        return await AzureBlobFileStoreAction(action, self.container_client, self.location, self.base_path).run(context)

    def _create_service_client(self) -> BlobServiceClient:
        from azure.storage.blob.aio import BlobServiceClient
        from azure.identity.aio import DefaultAzureCredential

        if self.config.connection_string:
            return BlobServiceClient.from_connection_string(self.config.connection_string)

        account_url = f"https://{self.config.account_name}.blob.core.windows.net"

        if self.config.account_key:
            return BlobServiceClient(account_url=account_url, credential=self.config.account_key)

        # Fall back to DefaultAzureCredential (env vars, managed identity, etc.)
        return BlobServiceClient(account_url=account_url, credential=DefaultAzureCredential())
