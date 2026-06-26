from typing import Optional, Dict, List, Tuple, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import LocalFileStoreComponentConfig
from mindor.dsl.schema.action import FileStoreActionConfig, LocalFileStoreActionConfig
from mindor.core.foundation.streaming.resources import ChunkedStreamResource
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.foundation.streaming.resources import save_stream_to_file
from mindor.core.foundation.streaming.resolver import resolve_stream_resource
from mindor.core.utils.files import list_dir, walk_dir, is_glob_match, is_path_within, guess_content_type
from mindor.core.utils.time import format_datetime_iso_string
from ..base import FileStoreService, FileStoreDriver, register_file_store_service
from ..base import ComponentActionContext
from .common import FileStoreAction
import aiofiles, os, stat as stat_module, sys, urllib.parse

_DEFAULT_CHUNK_SIZE = 8 * 1024 * 1024  # 8MB — for put and save_to downloads
_DEFAULT_STREAMING_CHUNK_SIZE = 8 * 1024  # 8KB — for streaming output, matching other StreamResources

class LocalFileStoreAction(FileStoreAction):
    def __init__(self, config: LocalFileStoreActionConfig, base_path: str):
        super().__init__(config)
        self.base_path: str = base_path  # absolute, normalized

    async def _put(self, context: ComponentActionContext) -> Dict[str, Any]:
        path         = await context.render_variable(self.config.path)
        source       = await context.render_variable(self.config.source)
        content_type = await context.render_variable(self.config.content_type)
        chunk_size   = await context.render_size(self.config.chunk_size, _DEFAULT_CHUNK_SIZE)

        source = await resolve_stream_resource(source) if source is not None else None

        if source is None:
            raise ValueError("'source' is required for 'put' action")

        absolute_path = self._resolve_absolute_path(path)

        if not is_path_within(self.base_path, absolute_path):
            raise PermissionError(f"Path escapes the allowed root directory: {path!r}")

        if os.path.isdir(absolute_path):
            raise IsADirectoryError(f"Cannot overwrite an existing directory: {path!r}")

        url = self._build_file_url(absolute_path)
        content_type = content_type or guess_content_type(path) or source.content_type

        os.makedirs(os.path.dirname(absolute_path) or self.base_path, exist_ok=True)

        tmp_path = f"{absolute_path}.tmp"
        try:
            await save_stream_to_file(ChunkedStreamResource(source, chunk_size), tmp_path)
            os.replace(tmp_path, absolute_path)
        except BaseException:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            raise

        size = os.path.getsize(absolute_path)

        return {
            "path": path,
            "url": url,
            "size": size,
            "content_type": content_type,
        }

    async def _get(self, context: ComponentActionContext) -> Dict[str, Any]:
        path       = await context.render_variable(self.config.path)
        save_to    = await context.render_variable(self.config.save_to)
        streaming  = await context.render_variable(self.config.streaming)
        chunk_size = await context.render_size(self.config.chunk_size)

        absolute_path = self._resolve_absolute_path(path)

        if not is_path_within(self.base_path, absolute_path):
            raise PermissionError(f"Path escapes the allowed root directory: {path!r}")

        try:
            stat = os.stat(absolute_path)
        except FileNotFoundError:
            raise FileNotFoundError(f"File not found: {path!r}")

        if not stat_module.S_ISREG(stat.st_mode):
            raise IsADirectoryError(f"Path is not a file: {path!r}")

        url = self._build_file_url(absolute_path)
        modified_at = format_datetime_iso_string(stat.st_mtime)
        content_type = guess_content_type(path)

        if save_to:
            if os.path.isdir(save_to):
                save_to = os.path.join(save_to, os.path.basename(path))

            parent = os.path.dirname(os.path.abspath(save_to))
            if parent:
                os.makedirs(parent, exist_ok=True)

            stream = FileStreamResource(absolute_path, chunk_size=chunk_size or _DEFAULT_CHUNK_SIZE)
            await save_stream_to_file(stream, save_to)

            return {
                "path": path,
                "url": url,
                "size": stat.st_size,
                "content_type": content_type,
                "modified_at": modified_at,
                "save_to": save_to,
            }

        if streaming:
            content = FileStreamResource(
                absolute_path,
                content_type=content_type,
                filename=os.path.basename(path),
                chunk_size=chunk_size or _DEFAULT_STREAMING_CHUNK_SIZE,
            )

            return {
                "path": path,
                "url": url,
                "size": stat.st_size,
                "content_type": content_type,
                "modified_at": modified_at,
                "content": content,
            }

        async with aiofiles.open(absolute_path, "rb") as file:
            content = await file.read()

        return {
            "path": path,
            "url": url,
            "size": stat.st_size,
            "content_type": content_type,
            "modified_at": modified_at,
            "content": content,
        }

    async def _delete(self, context: ComponentActionContext) -> Dict[str, Any]:
        path = await context.render_variable(self.config.path)

        absolute_path = self._resolve_absolute_path(path)

        if not is_path_within(self.base_path, absolute_path):
            raise PermissionError(f"Path escapes the allowed root directory: {path!r}")

        if os.path.exists(absolute_path):
            os.remove(absolute_path)

        return { "path": path }

    async def _exists(self, context: ComponentActionContext) -> Dict[str, Any]:
        path = await context.render_variable(self.config.path)

        absolute_path = self._resolve_absolute_path(path)

        if not is_path_within(self.base_path, absolute_path):
            raise PermissionError(f"Path escapes the allowed root directory: {path!r}")

        return { "path": path, "exists": os.path.exists(absolute_path) }

    async def _list(self, context: ComponentActionContext) -> Dict[str, Any]:
        path             = await context.render_variable(self.config.path)
        recursive        = await context.render_variable(self.config.recursive)
        pattern          = await context.render_variable(self.config.pattern)
        max_result_count = await context.render_variable(self.config.max_result_count)
        page_token       = await context.render_variable(self.config.next_token)

        list_path = self._resolve_absolute_path(path) if path else self.base_path

        if not is_path_within(self.base_path, list_path):
            raise PermissionError(f"Path escapes the allowed root directory: {path!r}")

        if not os.path.isdir(list_path):
            raise NotADirectoryError(f"Path is not a directory: {path!r}")

        start_index = int(page_token) if page_token else 0
        limit = int(max_result_count) if max_result_count is not None else sys.maxsize

        items: List[Dict[str, Any]] = []
        offset = 0

        async for dir, files in self._iter_files(list_path, recursive):
            for filename, stat in files:
                absolute_path = os.path.join(dir, filename)
                relative_path = os.path.relpath(absolute_path, self.base_path).replace(os.sep, "/")

                if pattern and not is_glob_match(relative_path, pattern):
                    continue

                if offset >= start_index:
                    items.append({
                        "path": relative_path,
                        "url": self._build_file_url(absolute_path),
                        "size": stat.st_size,
                        "content_type": guess_content_type(relative_path),
                        "modified_at": format_datetime_iso_string(stat.st_mtime),
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

    async def _iter_files(self, list_path: str, recursive: bool) -> AsyncIterator[Tuple[str, List[Tuple[str, os.stat_result]]]]:
        if recursive:
            async for dir, _, files in walk_dir(list_path):
                yield dir, files
        else:
            _, files = await list_dir(list_path)
            yield list_path, files

    def _resolve_absolute_path(self, path: str) -> str:
        return os.path.normpath(os.path.join(self.base_path, path))

    def _build_file_url(self, absolute_path: str) -> str:
        return f"file://{urllib.parse.quote(os.path.abspath(absolute_path))}"

@register_file_store_service(FileStoreDriver.LOCAL)
class LocalFileStoreService(FileStoreService):
    def __init__(self, id: str, config: LocalFileStoreComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.base_path: str = os.path.abspath(config.base_path or os.getcwd())

    async def _start(self) -> None:
        os.makedirs(self.base_path, exist_ok=True)
        await super()._start()

    async def _run(self, action: FileStoreActionConfig, context: ComponentActionContext) -> Any:
        return await LocalFileStoreAction(action, self.base_path).run(context)
