from __future__ import annotations

from typing import Optional, List, Any
from mindor.dsl.schema.component import ModelMemoryComponentConfig
from mindor.dsl.schema.component import ModelMemoryWindowConfig, ModelMemorySummaryConfig
from mindor.dsl.schema.action import ActionConfig, ModelMemoryActionConfig, ModelMemoryActionMethod
from mindor.core.logger import logging
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .buffer.base import ModelMemoryBuffer, ModelMemoryBufferRegistry
from .storage.base import ModelMemoryStorage, ModelMemoryStorageRegistry
import ulid, json

class ModelMemoryAction:
    def __init__(
        self,
        config: ModelMemoryActionConfig,
        window_config: Optional[ModelMemoryWindowConfig],
        summary_config: Optional[ModelMemorySummaryConfig],
        summary_component: Optional[ComponentService],
    ):
        self.config: ModelMemoryActionConfig = config
        self.window_config: Optional[ModelMemoryWindowConfig] = window_config
        self.summary_config: Optional[ModelMemorySummaryConfig] = summary_config
        self.summary_component: Optional[ComponentService] = summary_component

    async def run(self, context: ComponentActionContext, buffer: ModelMemoryBuffer, storage: ModelMemoryStorage) -> Any:
        session_id = await context.render_variable(self.config.session_id)

        if not session_id:
            raise ValueError(f"'session_id' is required for '{self.config.method.value}' method")

        result = await self._dispatch(context, self.config.method, session_id, buffer, storage)
        context.register_source("result", result)

        return (await context.render_variable(self.config.output)) if self.config.output else result

    async def _dispatch(
        self,
        context: ComponentActionContext,
        method: ModelMemoryActionMethod,
        session_id: str,
        buffer: ModelMemoryBuffer,
        storage: ModelMemoryStorage,
    ) -> Any:
        if method == ModelMemoryActionMethod.LOAD:
            # Buffer is source of truth: check buffer first
            turns = await buffer.get_turns(session_id)

            if turns is not None:
                summary = await buffer.get_summary(session_id) or ""
            else:
                # Not in buffer: load from storage and populate buffer
                turns, summary = await storage.load(session_id)
                await buffer.set_turns(session_id, turns)
                await buffer.set_summary(session_id, summary)
                await buffer.take_snapshot(session_id)

            if self.window_config:
                turns, _ = self._split_turns_by_window(turns, self.window_config)

            if self.summary_config and not self.window_config: # summary-only
                turns = []

            return { "summary": summary, "messages": self._flatten_turns(turns) }

        if method == ModelMemoryActionMethod.APPEND:
            messages = await context.render_variable(self.config.messages)

            if messages is None:
                raise ValueError("'messages' is required for 'append' method")

            if not isinstance(messages, list):
                raise TypeError(f"'messages' must be a list after rendering, got {type(messages).__name__}")

            turns = await buffer.get_turns(session_id)

            if turns is None:
                raise LookupError(f"Session not loaded: {session_id}. Call load before append.")

            await buffer.append_turn(session_id, messages)

            if self.window_config or self.summary_config:
                await self._prune_and_summarize(context, session_id, buffer)

            return None

        if method == ModelMemoryActionMethod.SAVE:
            messages = (await context.render_variable(self.config.messages)) if self.config.messages is not None else None

            if messages is not None and not isinstance(messages, list):
                raise TypeError(f"'messages' must be a list after rendering, got {type(messages).__name__}")

            turns = await buffer.get_turns(session_id)

            if turns is None:
                raise LookupError(f"Session not loaded: {session_id}. Call load before save.")

            if messages is not None:
                await buffer.append_turn(session_id, messages)

                if self.window_config or self.summary_config:
                    await self._prune_and_summarize(context, session_id, buffer)

            turns = await buffer.get_turns(session_id)
            summary = await buffer.get_summary(session_id) or ""
            await storage.save(session_id, turns=turns, summary=summary)

            await buffer.merge_buffer(session_id)
            await buffer.take_snapshot(session_id)

            return None

        if method == ModelMemoryActionMethod.CLEAR:
            turns = await buffer.get_turns(session_id)

            if turns is not None:
                await buffer.restore_snapshot(session_id)

            return None

        if method == ModelMemoryActionMethod.DELETE:
            await storage.delete(session_id)
            await buffer.remove(session_id)

            return None

        raise ValueError(f"Unsupported model memory action method: {method}")

    async def _prune_and_summarize(self, context: ComponentActionContext, session_id: str, buffer: ModelMemoryBuffer) -> None:
        turns = await buffer.get_turns(session_id)

        # summary-only: summarize everything, clear turns
        if self.summary_config and not self.window_config:
            if turns:
                previous_summary = await buffer.get_summary(session_id) or ""
                summary = await self._summarize_turns(context, turns, previous_summary, self.summary_config)
                await buffer.set_turns(session_id, [])
                await buffer.set_summary(session_id, summary)
            return

        # window: prune excess turns
        recent_turns, older_turns = self._split_turns_by_window(turns, self.window_config)

        if not older_turns:
            return

        if self.summary_config:
            previous_summary = await buffer.get_summary(session_id) or ""
            summary = await self._summarize_turns(context, older_turns, previous_summary, self.summary_config)
            await buffer.set_summary(session_id, summary)

        # Replace with windowed turns only
        await buffer.set_turns(session_id, recent_turns)

    async def _summarize_turns(self,
        context: ComponentActionContext,
        turns: List[List[Any]],
        previous_summary: str,
        summary_config: ModelMemorySummaryConfig
    ) -> str:
        instruction = await context.render_variable(summary_config.instruction)

        if summary_config.input is None:
            # Default mode: synthesize a complete messages array and pass it through.
            instruction_section = instruction or "Summarize the following conversation concisely:"
            summary_section = f"Previous summary:\n{previous_summary}" if previous_summary else ""
            system_prompt = "\n\n".join(section for section in [ instruction_section, summary_section ] if section)
            messages = []

            if system_prompt:
                messages.append({ "role": "system", "content": system_prompt })

            messages.extend(self._flatten_turns(turns))

            input = { "messages": messages }
        else:
            # Explicit mode: expose raw sources, let user assemble via input mapping.
            context.register_source("messages", self._flatten_turns(turns))
            context.register_source("instruction", instruction)
            context.register_source("previous_summary", previous_summary)

            input = await context.render_variable(summary_config.input)

        response = await self.summary_component.run(summary_config.action, ulid.ulid(), input)

        if not isinstance(response, str):
            logging.warning("Summary component '%s' returned %s, expected str", summary_config.component, type(response).__name__)
            try:
                response = json.dumps(response, ensure_ascii=False)
            except (TypeError, ValueError):
                response = str(response)

        return response

    def _split_turns_by_window(self, turns: List[List[Any]], window_config: ModelMemoryWindowConfig):
        recent_turns = []
        message_count = 0

        for turn in reversed(turns):
            if window_config.max_turn_count and len(recent_turns) >= window_config.max_turn_count:
                break
            if window_config.max_message_count and message_count + len(turn) > window_config.max_message_count:
                break
            recent_turns.insert(0, turn)
            message_count += len(turn)

        # Always preserve at least the latest turn
        if not recent_turns and turns:
            recent_turns = [turns[-1]]

        return recent_turns, turns[:len(turns) - len(recent_turns)]

    def _flatten_turns(self, turns: List[List[Any]]) -> List[Any]:
        return [ message for turn in turns for message in turn ]

@register_component(ComponentType.MODEL_MEMORY)
class ModelMemoryComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: ModelMemoryComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self._buffer: ModelMemoryBuffer   = self._create_buffer()
        self._storage: ModelMemoryStorage = self._create_storage()
        self._summary_component: Optional[ComponentService] = None

    def _get_setup_requirements(self) -> Optional[List[str]]:
        buffer_requirements  = self._buffer.get_setup_requirements()
        storage_requirements = self._storage.get_setup_requirements()

        return [ *(buffer_requirements or []), *(storage_requirements or []) ] or None

    async def _start(self) -> None:
        if self.config.summary:
            self._summary_component = self._create_component(self.config.summary.component)

        await self._buffer.setup()
        await self._storage.setup()

        await super()._start()

    async def _stop(self) -> None:
        await super()._stop()

        await self._buffer.close()
        await self._storage.close()

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return await ModelMemoryAction(action, self.config.window, self.config.summary, self._summary_component).run(context, self._buffer, self._storage)

    def _create_buffer(self) -> ModelMemoryBuffer:
        if not ModelMemoryBufferRegistry:
            from . import buffer
        try:
            return ModelMemoryBufferRegistry[self.config.buffer.driver](self.config.buffer)
        except KeyError:
            raise ValueError(f"Unsupported model memory buffer driver: {self.config.buffer.driver}")

    def _create_storage(self) -> ModelMemoryStorage:
        if not ModelMemoryStorageRegistry:
            from . import storage
        try:
            return ModelMemoryStorageRegistry[self.config.storage.driver](self.config.storage)
        except KeyError:
            raise ValueError(f"Unsupported model memory storage driver: {self.config.storage.driver}")
