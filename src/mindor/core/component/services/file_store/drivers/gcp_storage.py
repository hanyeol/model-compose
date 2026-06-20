from __future__ import annotations
from typing import TYPE_CHECKING

from dataclasses import dataclass
from typing import Optional, Dict, List, Any
from mindor.dsl.schema.component import GcpStorageFileStoreComponentConfig
from mindor.dsl.schema.action import FileStoreActionConfig, GcpStorageFileStoreActionConfig
from mindor.core.utils.streaming.stream import save_stream_to_file
from mindor.core.utils.streaming.resolver import resolve_stream_resource
from mindor.core.utils.streaming.bytes import BytesStreamResource
from mindor.core.utils.files import is_glob_match, guess_content_type
from mindor.core.utils.time import format_datetime_iso_string
from mindor.core.utils.providers.gcp_storage import upload, multipart_upload
from ..base import FileStoreService, FileStoreDriver, register_file_store_service
from ..base import ComponentActionContext
from .common import FileStoreAction
import aiohttp, os, urllib.parse

if TYPE_CHECKING:
    from gcloud.aio.storage import Storage

_DEFAULT_CHUNK_SIZE = 8 * 1024 * 1024  # 8MB — for put and save_to downloads
_DEFAULT_STREAMING_CHUNK_SIZE = 8 * 1024  # 8KB — for streaming output, matching other StreamResources
_DEFAULT_MULTIPART_THRESHOLD = 8 * 1024 * 1024  # 8MB

@dataclass(frozen=True)
class GcsLocation:
    bucket: str
    project: Optional[str] = None
    endpoint: Optional[str] = None

class GcpStorageFileStoreAction(FileStoreAction):
    def __init__(
        self,
        config: GcpStorageFileStoreActionConfig,
        client: Storage,
        location: GcsLocation,
        base_path: Optional[str] = None,
    ):
        super().__init__(config)
        self.client: Storage = client
        self.location: GcsLocation = location
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

        object_name   = self._resolve_object_name(path)
        content_type  = content_type or guess_content_type(path) or source.content_type
        use_multipart = source.size is None or source.size > multipart_threshold

        if use_multipart:
            uploaded_size = await multipart_upload(
                self.client,
                self.location.bucket,
                object_name,
                source,
                chunk_size=chunk_size,
                content_type=content_type,
                metadata=metadata,
            )
        else:
            uploaded_size = await upload(
                self.client,
                self.location.bucket,
                object_name,
                source,
                content_type=content_type,
                metadata=metadata,
            )

        return {
            "path": path,
            "url": self._build_file_url(object_name),
            "size": uploaded_size,
            "content_type": content_type,
        }

    async def _get(self, context: ComponentActionContext) -> Dict[str, Any]:
        from mindor.core.utils.streaming.stream import ReaderStreamResource

        path       = await context.render_variable(self.config.path)
        save_to    = await context.render_variable(self.config.save_to)
        streaming  = await context.render_variable(self.config.streaming)
        chunk_size = await context.render_size(self.config.chunk_size)

        object_name = self._resolve_object_name(path)

        metadata = await self.client.download_metadata(self.location.bucket, object_name)

        size_raw = metadata.get("size")
        size = int(size_raw) if size_raw is not None else None
        content_type = metadata.get("contentType") or guess_content_type(path)
        last_modified = metadata.get("updated") or metadata.get("timeCreated")
        modified_at = last_modified  # GCS already returns RFC 3339 strings
        url = self._build_file_url(object_name)

        if save_to:
            if os.path.isdir(save_to):
                save_to = os.path.join(save_to, os.path.basename(path))

            parent = os.path.dirname(os.path.abspath(save_to))
            if parent:
                os.makedirs(parent, exist_ok=True)

            data = await self.client.download(self.location.bucket, object_name)
            stream = BytesStreamResource(data, chunk_size=chunk_size or _DEFAULT_CHUNK_SIZE)
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
            data = await self.client.download(self.location.bucket, object_name)
            content = BytesStreamResource(
                data,
                content_type=content_type,
                filename=os.path.basename(path) or None,
                chunk_size=chunk_size or _DEFAULT_STREAMING_CHUNK_SIZE,
            )

            return {
                "path": path,
                "url": url,
                "size": size if size is not None else len(data),
                "content_type": content_type,
                "modified_at": modified_at,
                "content": content,
            }

        content = await self.client.download(self.location.bucket, object_name)

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

        object_name = self._resolve_object_name(path)

        await self.client.delete(self.location.bucket, object_name)

        return { "path": path }

    async def _exists(self, context: ComponentActionContext) -> Dict[str, Any]:
        from aiohttp import ClientResponseError

        path = await context.render_variable(self.config.path)

        object_name = self._resolve_object_name(path)

        try:
            await self.client.download_metadata(self.location.bucket, object_name)
            exists = True
        except ClientResponseError as e:
            if e.status == 404:
                exists = False
            else:
                raise

        return { "path": path, "exists": exists }

    async def _list(self, context: ComponentActionContext) -> Dict[str, Any]:
        path             = await context.render_variable(self.config.path)
        recursive        = await context.render_variable(self.config.recursive)
        pattern          = await context.render_variable(self.config.pattern)
        max_result_count = await context.render_variable(self.config.max_result_count)
        next_token       = await context.render_variable(self.config.next_token)

        name_prefix = self._resolve_object_name(path) if path else (self.base_path or "")

        list_params: Dict[str, Any] = {}
        if name_prefix:
            list_params["prefix"] = name_prefix
        if not recursive:
            list_params["delimiter"] = "/"
        if max_result_count is not None:
            list_params["maxResults"] = int(max_result_count)
        if next_token:
            list_params["pageToken"] = next_token

        response = await self.client.list_objects(self.location.bucket, params=list_params)

        items: List[Dict[str, Any]] = []
        for blob in response.get("items", []) or []:
            object_name = blob["name"]
            relative_path = self._resolve_relative_path(object_name)
            size_raw = blob.get("size")
            last_modified = blob.get("updated") or blob.get("timeCreated")

            if pattern and not is_glob_match(relative_path, pattern):
                continue

            items.append({
                "path": relative_path,
                "url": self._build_file_url(object_name),
                "size": int(size_raw) if size_raw is not None else None,
                "content_type": blob.get("contentType") or guess_content_type(relative_path),
                "modified_at": last_modified,
            })

        return {
            "items": items,
            "count": len(items),
            "next_token": response.get("nextPageToken"),
        }

    def _resolve_object_name(self, path: str) -> str:
        if self.base_path:
            return f"{self.base_path}{path.lstrip('/')}"

        return path

    def _resolve_relative_path(self, object_name: str) -> str:
        if self.base_path and object_name.startswith(self.base_path):
            return object_name[len(self.base_path):]

        return object_name

    def _build_file_url(self, object_name: str) -> str:
        quoted_object_name = urllib.parse.quote(object_name, safe="/")
        host = (self.location.endpoint or "https://storage.googleapis.com").rstrip("/")
        return f"{host}/{self.location.bucket}/{quoted_object_name}"

@register_file_store_service(FileStoreDriver.GCP_STORAGE)
class GcpStorageFileStoreService(FileStoreService):
    def __init__(self, id: str, config: GcpStorageFileStoreComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.config: GcpStorageFileStoreComponentConfig = config
        self.location: GcsLocation = GcsLocation(
            bucket=config.bucket,
            project=config.project,
            endpoint=config.endpoint.rstrip("/") if config.endpoint else None,
        )
        self.base_path: Optional[str] = (config.base_path.rstrip("/") + "/") if config.base_path else None
        self.client: Optional[Storage] = None
        self.session: Optional[aiohttp.ClientSession] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "gcloud-aio-storage" ]

    async def _start(self) -> None:
        self.client, self.session = self._create_client()
        await super()._start()

    async def _stop(self) -> None:
        await super()._stop()
        if self.client is not None:
            try:
                await self.client.close()
            finally:
                self.client = None
        if self.session is not None:
            try:
                await self.session.close()
            finally:
                self.session = None

    async def _run(self, action: FileStoreActionConfig, context: ComponentActionContext) -> Any:
        return await GcpStorageFileStoreAction(action, self.client, self.location, self.base_path).run(context)

    def _create_client(self) -> Tuple[Storage, aiohttp.ClientSession]:
        from gcloud.aio.storage import Storage

        session = aiohttp.ClientSession()
        client_params: Dict[str, Any] = { "session": session }
        if self.config.credentials_path:
            client_params["service_file"] = self.config.credentials_path
        if self.location.endpoint:
            client_params["api_root"] = self.location.endpoint

        return Storage(**client_params), session
