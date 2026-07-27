from __future__ import annotations

from typing import Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.action import SearchEngineActionConfig, SearchEngineActionMethod
from ..base import ComponentActionContext
from ....action.base import ComponentAction

class SearchEngineAction(ComponentAction):
    def __init__(self, config: SearchEngineActionConfig):
        self.config: SearchEngineActionConfig = config

    async def run(self, context: ComponentActionContext, database: Any) -> Any:
        params = await self._resolve_params(self.config.method, context)

        is_direct_output = not self.config.output or self.config.output == "${result}"

        result = await self._dispatch(self.config.method, database, params)
        context.register_source("result", result)

        return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, method: SearchEngineActionMethod, context: ComponentActionContext) -> Dict[str, Any]:
        if method == SearchEngineActionMethod.INDEX:
            index     = await context.render_variable(self.config.index)
            documents = await context.render_variable(self.config.documents)

            if documents is None:
                raise ValueError("'documents' must be specified for 'index' method")

            return {
                "index":     index,
                "documents": documents,
            }

        if method == SearchEngineActionMethod.SEARCH:
            index         = await context.render_variable(self.config.index)
            query         = await context.render_variable(self.config.query)
            limit         = await context.render_variable(self.config.limit)
            search_fields = await context.render_variable(self.config.search_fields)

            if query is None:
                raise ValueError("'query' must be specified for 'search' method")

            return {
                "index":         index,
                "query":         query,
                "limit":         limit,
                "search_fields": search_fields,
            }

        if method == SearchEngineActionMethod.DELETE:
            index        = await context.render_variable(self.config.index)
            document_ids = await context.render_variable(self.config.document_ids)

            if document_ids is None:
                raise ValueError("'document_ids' must be specified for 'delete' method")

            return {
                "index":        index,
                "document_ids": document_ids,
            }

        raise ValueError(f"Unsupported search engine action method: {method}")

    async def _dispatch(self, method: SearchEngineActionMethod, database: Any, params: Dict[str, Any]) -> Any:
        if method == SearchEngineActionMethod.INDEX:
            return await self._index(database, params)

        if method == SearchEngineActionMethod.SEARCH:
            return await self._search(database, params)

        if method == SearchEngineActionMethod.DELETE:
            return await self._delete(database, params)

        raise ValueError(f"Unsupported search engine action method: {method}")

    @abstractmethod
    async def _index(self, database: Any, params: Dict[str, Any]) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _search(self, database: Any, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    async def _delete(self, database: Any, params: Dict[str, Any]) -> Dict[str, Any]:
        pass
