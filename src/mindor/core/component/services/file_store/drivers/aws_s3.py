from __future__ import annotations
from typing import TYPE_CHECKING

from dataclasses import dataclass
from typing import Optional, Dict, List, Any
from mindor.dsl.schema.component import AwsS3FileStoreComponentConfig
from mindor.dsl.schema.action import FileStoreActionConfig, AwsS3FileStoreActionConfig
from mindor.core.foundation.streaming.resources import ReaderStreamResource, save_stream_to_file
from mindor.core.foundation.streaming.resolver import resolve_stream_resource
from mindor.core.utils.files import is_glob_match, guess_content_type
from mindor.core.utils.time import format_datetime_iso_string
from mindor.core.foundation.providers.aws_s3 import upload, multipart_upload
from ..base import FileStoreService, FileStoreDriver, register_file_store_service
from ..base import ComponentActionContext
from .common import FileStoreAction
from contextlib import AsyncExitStack
import os, urllib.parse

if TYPE_CHECKING:
    from types_aiobotocore_s3 import S3Client

_DEFAULT_CHUNK_SIZE = 8 * 1024 * 1024  # 8MB — for put and save_to downloads
_DEFAULT_STREAMING_CHUNK_SIZE = 8 * 1024  # 8KB — for streaming output, matching other StreamResources
_DEFAULT_MULTIPART_THRESHOLD = 8 * 1024 * 1024  # 8MB

@dataclass(frozen=True)
class S3Location:
    bucket: str
    region: Optional[str] = None
    endpoint: Optional[str] = None

class AwsS3FileStoreAction(FileStoreAction):
    def __init__(
        self,
        config: AwsS3FileStoreActionConfig,
        client: S3Client,
        location: S3Location,
        base_path: Optional[str] = None,
    ):
        super().__init__(config)
        self.client: S3Client = client
        self.location: S3Location = location
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

        object_key    = self._resolve_object_key(path)
        content_type  = content_type or guess_content_type(path) or source.content_type
        use_multipart = source.size is None or source.size > multipart_threshold

        if use_multipart:
            uploaded_size = await multipart_upload(
                self.client,
                self.location.bucket,
                object_key,
                source,
                chunk_size=chunk_size,
                content_type=content_type,
                metadata=metadata,
            )
        else:
            uploaded_size = await upload(
                self.client,
                self.location.bucket,
                object_key,
                source,
                content_type=content_type,
                metadata=metadata,
            )

        return {
            "path": path,
            "url": self._build_file_url(object_key),
            "size": uploaded_size,
            "content_type": content_type,
        }

    async def _get(self, context: ComponentActionContext) -> Dict[str, Any]:
        path       = await context.render_variable(self.config.path)
        save_to    = await context.render_variable(self.config.save_to)
        streaming  = await context.render_variable(self.config.streaming)
        chunk_size = await context.render_size(self.config.chunk_size)

        object_key = self._resolve_object_key(path)
        response = await self.client.get_object(Bucket=self.location.bucket, Key=object_key)

        body = response["Body"]
        size = response.get("ContentLength")
        content_type = response.get("ContentType") or guess_content_type(path)
        last_modified = response.get("LastModified")
        modified_at = format_datetime_iso_string(last_modified) if last_modified else None
        url = self._build_file_url(object_key)

        if save_to:
            if os.path.isdir(save_to):
                save_to = os.path.join(save_to, os.path.basename(path))

            parent = os.path.dirname(os.path.abspath(save_to))
            if parent:
                os.makedirs(parent, exist_ok=True)

            stream = ReaderStreamResource(body, chunk_size=chunk_size or _DEFAULT_CHUNK_SIZE)
            await save_stream_to_file(stream, save_to)

            return {
                "path": path,
                "url": url,
                "size": size or os.path.getsize(save_to),
                "content_type": content_type,
                "modified_at": modified_at,
                "save_to": save_to,
            }

        if streaming:
            content = ReaderStreamResource(
                body,
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

        content = await body.read()

        return {
            "path": path,
            "url": url,
            "size": size or len(content),
            "content_type": content_type,
            "modified_at": modified_at,
            "content": content,
        }

    async def _delete(self, context: ComponentActionContext) -> Dict[str, Any]:
        path = await context.render_variable(self.config.path)

        object_key = self._resolve_object_key(path)

        await self.client.delete_object(
            Bucket=self.location.bucket,
            Key=object_key
        )

        return { "path": path }

    async def _exists(self, context: ComponentActionContext) -> Dict[str, Any]:
        from botocore.exceptions import ClientError

        path = await context.render_variable(self.config.path)

        object_key = self._resolve_object_key(path)

        try:
            await self.client.head_object(Bucket=self.location.bucket, Key=object_key)
            exists = True
        except ClientError as e:
            response = e.response or {}
            code = response.get("Error", {}).get("Code")
            status = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            # HEAD returns "404"; GET returns "NoSuchKey"; some S3-compatible stores return "NotFound"
            if code in ("404", "NoSuchKey", "NotFound") or status == 404:
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

        key_prefix = self._resolve_object_key(path) if path else (self.base_path or "")

        list_params: Dict[str, Any] = { "Bucket": self.location.bucket }
        if key_prefix:
            list_params["Prefix"] = key_prefix
        if not recursive:
            list_params["Delimiter"] = "/"
        if max_result_count is not None:
            list_params["MaxKeys"] = int(max_result_count)
        if next_token:
            list_params["ContinuationToken"] = next_token

        response = await self.client.list_objects_v2(**list_params)
        contents = response.get("Contents", []) or []

        items: List[Dict[str, Any]] = []
        for content in contents:
            object_key = content["Key"]
            relative_path = self._resolve_relative_path(object_key)
            last_modified = content.get("LastModified")

            if pattern and not is_glob_match(relative_path, pattern):
                continue

            items.append({
                "path": relative_path,
                "url": self._build_file_url(object_key),
                "size": content.get("Size"),
                "content_type": guess_content_type(relative_path),
                "modified_at": format_datetime_iso_string(last_modified) if last_modified else None,
            })

        return {
            "items": items,
            "count": len(items),
            "next_token": response.get("NextContinuationToken"),
        }

    def _resolve_object_key(self, path: str) -> str:
        if self.base_path:
            return f"{self.base_path}{path.lstrip('/')}"

        return path

    def _resolve_relative_path(self, object_key: str) -> str:
        if self.base_path and object_key.startswith(self.base_path):
            return object_key[len(self.base_path):]

        return object_key

    def _build_file_url(self, object_key: str) -> str:
        quoted_object_key = urllib.parse.quote(object_key, safe="/")

        if self.location.endpoint:
            return f"{self.location.endpoint}/{self.location.bucket}/{quoted_object_key}"

        if self.location.region:
            return f"https://{self.location.bucket}.s3.{self.location.region}.amazonaws.com/{quoted_object_key}"

        return f"https://s3.amazonaws.com/{self.location.bucket}/{quoted_object_key}"

@register_file_store_service(FileStoreDriver.AWS_S3)
class AwsS3FileStoreService(FileStoreService):
    def __init__(self, id: str, config: AwsS3FileStoreComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.config: AwsS3FileStoreComponentConfig = config
        self.location: S3Location = S3Location(
            bucket=config.bucket,
            region=config.region,
            endpoint=config.endpoint.rstrip("/") if config.endpoint else None,
        )
        self.base_path: Optional[str] = (config.base_path.rstrip("/") + "/") if config.base_path else None
        self.client: Optional[S3Client] = None

        self._client_session: Optional[AsyncContextManager[S3Client]] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "aioboto3" ]

    async def _start(self) -> None:
        self._client_session = self._create_client_session()
        self.client = await self._client_session.__aenter__()
        await super()._start()

    async def _stop(self) -> None:
        await super()._stop()
        if self._client_session is not None:
            try:
                await self._client_session.__aexit__(None, None, None)
            finally:
                self._client_session = None
                self.client = None

    async def _run(self, action: FileStoreActionConfig, context: ComponentActionContext) -> Any:
        return await AwsS3FileStoreAction(action, self.client, self.location, self.base_path).run(context)

    def _create_client_session(self) -> AsyncContextManager[S3Client]:
        import aioboto3

        client_params: Dict[str, Any] = {}
        if self.config.region:
            client_params["region_name"] = self.config.region
        if self.config.endpoint:
            client_params["endpoint_url"] = self.config.endpoint
        if self.config.access_key_id:
            client_params["aws_access_key_id"] = self.config.access_key_id
        if self.config.secret_access_key:
            client_params["aws_secret_access_key"] = self.config.secret_access_key
        if self.config.session_token:
            client_params["aws_session_token"] = self.config.session_token

        return aioboto3.Session().client("s3", **client_params)
