from __future__ import annotations

from typing import Dict, Any
from abc import abstractmethod
from mindor.dsl.schema.action import FileStoreActionConfig, FileStoreActionMethod
from ..base import ComponentActionContext
from ....action.base import ComponentAction

class FileStoreAction(ComponentAction):
    def __init__(self, config: FileStoreActionConfig):
        self.config: FileStoreActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        params = await self._resolve_params(self.config.method, context)

        is_direct_output = not self.config.output or self.config.output == "${result}"

        result = await self._dispatch(self.config.method, params)
        context.register_source("result", result)

        return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, method: FileStoreActionMethod, context: ComponentActionContext) -> Dict[str, Any]:
        if method == FileStoreActionMethod.PUT:
            path                = await context.render_variable(self.config.path)
            source              = await context.render_variable(self.config.source)
            content_type        = await context.render_variable(self.config.content_type)
            metadata            = await context.render_variable(self.config.metadata)
            multipart_threshold = await context.render_scalar(self.config.multipart_threshold, "size")
            chunk_size          = await context.render_scalar(self.config.chunk_size, "size")

            return {
                "path":                path,
                "source":              source,
                "content_type":        content_type,
                "metadata":            metadata,
                "multipart_threshold": multipart_threshold,
                "chunk_size":          chunk_size,
            }

        if method == FileStoreActionMethod.GET:
            path       = await context.render_variable(self.config.path)
            save_to    = await context.render_variable(self.config.save_to)
            streaming  = await context.render_variable(self.config.streaming)
            chunk_size = await context.render_scalar(self.config.chunk_size, "size")

            return {
                "path":       path,
                "save_to":    save_to,
                "streaming":  streaming,
                "chunk_size": chunk_size,
            }

        if method == FileStoreActionMethod.DELETE:
            path = await context.render_variable(self.config.path)

            return {
                "path": path,
            }

        if method == FileStoreActionMethod.EXISTS:
            path = await context.render_variable(self.config.path)

            return {
                "path": path,
            }

        if method == FileStoreActionMethod.LIST:
            path             = await context.render_variable(self.config.path)
            recursive        = await context.render_variable(self.config.recursive)
            pattern          = await context.render_variable(self.config.pattern)
            max_result_count = await context.render_variable(self.config.max_result_count)
            next_token       = await context.render_variable(self.config.next_token)

            return {
                "path":             path,
                "recursive":        recursive,
                "pattern":          pattern,
                "max_result_count": max_result_count,
                "next_token":       next_token,
            }

        raise ValueError(f"Unsupported file store action method: {method}")

    async def _dispatch(self, method: FileStoreActionMethod, params: Dict[str, Any]) -> Dict[str, Any]:
        if method == FileStoreActionMethod.PUT:
            return await self._put(params)

        if method == FileStoreActionMethod.GET:
            return await self._get(params)

        if method == FileStoreActionMethod.DELETE:
            return await self._delete(params)

        if method == FileStoreActionMethod.EXISTS:
            return await self._exists(params)

        if method == FileStoreActionMethod.LIST:
            return await self._list(params)

        raise ValueError(f"Unsupported file store action method: {method}")

    @abstractmethod
    async def _put(self, params: Dict[str, Any]) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _get(self, params: Dict[str, Any]) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _delete(self, params: Dict[str, Any]) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _exists(self, params: Dict[str, Any]) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        pass
