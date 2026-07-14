from __future__ import annotations

from typing import Dict, Any
from abc import abstractmethod
from mindor.dsl.schema.action import FileStoreActionConfig, FileStoreActionMethod
from ..base import ComponentActionContext

class FileStoreAction:
    def __init__(self, config: FileStoreActionConfig):
        self.config: FileStoreActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        is_direct_output = not self.config.output or self.config.output == "${result}"

        result = await self._dispatch(self.config.method, context)
        context.register_source("result", result)

        return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _dispatch(self, method: FileStoreActionMethod, context: ComponentActionContext) -> Dict[str, Any]:
        if method == FileStoreActionMethod.PUT:
            return await self._put(context)

        if method == FileStoreActionMethod.GET:
            return await self._get(context)

        if method == FileStoreActionMethod.DELETE:
            return await self._delete(context)

        if method == FileStoreActionMethod.EXISTS:
            return await self._exists(context)

        if method == FileStoreActionMethod.LIST:
            return await self._list(context)

        raise ValueError(f"Unsupported file store action method: {method}")

    @abstractmethod
    async def _put(self, context: ComponentActionContext) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _get(self, context: ComponentActionContext) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _delete(self, context: ComponentActionContext) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _exists(self, context: ComponentActionContext) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _list(self, context: ComponentActionContext) -> Dict[str, Any]:
        pass
