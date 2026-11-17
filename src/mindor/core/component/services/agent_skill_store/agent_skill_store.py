from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import AgentSkillStoreComponentConfig, AgentSkillRepositoryActions
from mindor.dsl.schema.action import (
    ActionConfig,
    AgentSkillStoreActionConfig,
    AgentSkillStoreActionMethod,
)
from mindor.core.foundation.streaming.iterators import StreamIterator, StreamChunkIterator
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .loader import AgentSkill, AgentSkillParser
import asyncio
import ulid

_SKILL_FILENAME = "SKILL.md"

class AgentSkillStoreAction:
    def __init__(
        self,
        config: AgentSkillStoreActionConfig,
        repository_component: ComponentService,
        repository_actions: AgentSkillRepositoryActions,
    ):
        self.config: AgentSkillStoreActionConfig = config
        self.repository_component: ComponentService = repository_component
        self.repository_actions: AgentSkillRepositoryActions = repository_actions

        self._parser: AgentSkillParser = AgentSkillParser()

    async def run(self, context: ComponentActionContext) -> Any:
        input, primary_input, is_single_input, is_streaming_input = await self._prepare_input(self.config.method, context)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(self.config.method, context)

        is_direct_output = not self.config.output or self.config.output == "${result}"

        if is_streaming_input:
            async def _stream_output_generator():
                async for batch_inputs in BatchSourceIterator(input, batch_size=batch_size or 1):
                    batch_inputs = zip(*batch_inputs) # Transpose per-slot batches into per-request tuples.
                    batch_results = await self._process_batch(self.config.method, batch_inputs, params, context.cancellation_token)
                    for result in batch_results:
                        context.register_source("result", result)
                        yield (await context.render_variable(self.config.output)) if not is_direct_output else result

            if isinstance(primary_input, StreamChunkIterator) and primary_input.is_fragmented:
                return StreamChunkIterator(_stream_output_generator(), is_fragmented=True)

            return _stream_output_generator()
        else:
            results: List[Any] = []
            async for batch_inputs in BatchSourceIterator(input, batch_size=batch_size or 1):
                batch_inputs = zip(*batch_inputs) # Transpose per-slot batches into per-request tuples.
                batch_results = await self._process_batch(self.config.method, batch_inputs, params, context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _prepare_input(
        self,
        method: AgentSkillStoreActionMethod,
        context: ComponentActionContext,
    ) -> Tuple[Any, Any, bool, bool]:
        if method == AgentSkillStoreActionMethod.LIST:
            tags = await context.render_text_array(self.config.tags, item_is_list=True, single_as_array=True)

            is_single_input    = tags is None or (isinstance(tags, list) and len(tags) == 1)
            is_streaming_input = isinstance(tags, (StreamIterator, AsyncIterator))

            return (tags,), tags, is_single_input, is_streaming_input

        if method == AgentSkillStoreActionMethod.GET:
            name = await context.render_variable(self.config.name)

            is_single_input    = not isinstance(name, (list, StreamIterator, AsyncIterator))
            is_streaming_input = isinstance(name, (StreamIterator, AsyncIterator))

            if is_single_input:
                name = [ name ]

            return (name,), name, is_single_input, is_streaming_input

        if method == AgentSkillStoreActionMethod.FIND:
            query = await context.render_variable(self.config.query)
            tags  = await context.render_text_array(self.config.tags, item_is_list=True, single_as_array=True)

            is_single_input    = not isinstance(query, (list, StreamIterator, AsyncIterator))
            is_streaming_input = isinstance(query, (StreamIterator, AsyncIterator))

            if is_single_input:
                query = [ query ]

            return (query, tags), query, is_single_input, is_streaming_input

        raise ValueError(f"Unsupported agent skill store action method: {method}")

    async def _resolve_params(
        self,
        method: AgentSkillStoreActionMethod,
        context: ComponentActionContext,
    ) -> Dict[str, Any]:
        if method == AgentSkillStoreActionMethod.FIND:
            return {
                "limit": self.config.limit,
            }

        return {}

    async def _process_batch(
        self,
        method: AgentSkillStoreActionMethod,
        inputs: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Any]:
        return await asyncio.gather(*[
            self._process(method, input, params, cancellation_token) for input in inputs
        ])

    async def _process(
        self,
        method: AgentSkillStoreActionMethod,
        input: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Any:
        if method == AgentSkillStoreActionMethod.LIST:
            return await self._list(*input, params=params, cancellation_token=cancellation_token)

        if method == AgentSkillStoreActionMethod.GET:
            return await self._get(*input, params=params, cancellation_token=cancellation_token)

        if method == AgentSkillStoreActionMethod.FIND:
            return await self._find(*input, params=params, cancellation_token=cancellation_token)

        raise ValueError(f"Unsupported agent skill store action method: {method}")

    async def _list(
        self,
        tags: Any,
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> List[Dict[str, Any]]:
        skills = await self._load_all_skills()

        if tags is not None:
            skills = self._filter_by_tags(skills, await tags.collect())
        
        return [ skill.to_dict() for skill in skills ]

    async def _get(
        self,
        name: str,
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> Dict[str, Any]:
        if not name:
            raise ValueError("'name' is required for 'get' method")

        skill = await self._load_skill(name)

        if skill is None:
            raise LookupError(f"Skill not found: {name}")

        return skill.to_dict()

    async def _find(
        self,
        query: str,
        tags: Any,
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> List[Dict[str, Any]]:
        if not query:
            raise ValueError("'query' is required for 'find' method")

        skills = await self._load_all_skills()

        if tags is not None:
            skills = self._filter_by_tags(skills, await tags.collect())

        skills = self._search(skills, query)

        if params["limit"] is not None:
            skills = skills[:params["limit"]]

        return [ skill.to_dict() for skill in skills ]

    async def _load_all_skills(self) -> List[AgentSkill]:
        """Fetch every skill directory from the repository and parse each SKILL.md."""
        response = await self.repository_component.run(
            self.repository_actions.list,
            ulid.ulid(),
            { "path": "", "recursive": True, "pattern": f"*/{_SKILL_FILENAME}" },
        )

        names = sorted({ item["path"].split("/", 1)[0] for item in response.get("items", []) })
        skills = await asyncio.gather(*[ self._load_skill(name) for name in names ])

        return [ skill for skill in skills if skill is not None ]

    async def _load_skill(self, name: str) -> Optional[AgentSkill]:
        """Fetch a single SKILL.md from the repository and parse it."""
        try:
            response = await self.repository_component.run(
                self.repository_actions.get,
                ulid.ulid(),
                { "path": f"{name}/{_SKILL_FILENAME}" },
            )
        except FileNotFoundError:
            return None

        content = response.get("content")

        if content is None:
            return None

        if isinstance(content, (bytes, bytearray)):
            content = content.decode("utf-8")

        return self._parser.parse(name, content)

    def _filter_by_tags(self, skills: List[AgentSkill], tags: Optional[List[str]]) -> List[AgentSkill]:
        if not tags:
            return skills
        
        tags = set(tags)

        return [ skill for skill in skills if tags.issubset(skill.tags) ]

    def _search(self, skills: List[AgentSkill], query: str) -> List[AgentSkill]:
        needle = query.strip().lower()

        if not needle:
            return []

        return [ skill for skill in skills if self._matches(skill, needle) ]

    def _matches(self, skill: AgentSkill, needle: str) -> bool:
        if needle in skill.name.lower():
            return True

        if needle in skill.description.lower():
            return True

        if any(needle in tag.lower() for tag in skill.tags):
            return True

        return False

@register_component(ComponentType.AGENT_SKILL_STORE)
class AgentSkillStoreComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: AgentSkillStoreComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self._repository_component: Optional[ComponentService] = None

    async def _start(self) -> None:
        self._repository_component = self._create_component(self.config.repository.component)

        await super()._start()

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return await AgentSkillStoreAction(
            action,
            self._repository_component,
            self.config.repository.actions
        ).run(context)
