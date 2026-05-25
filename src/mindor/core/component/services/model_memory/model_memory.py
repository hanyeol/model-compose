from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.component import ModelMemoryComponentConfig, ModelMemoryStorageDriver, ModelMemoryBufferDriver, ModelMemoryWindowConfig
from mindor.dsl.schema.action import ActionConfig, ModelMemoryActionConfig, ModelMemoryActionMethod
from mindor.core.component import ComponentResolver, create_component
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .buffer.base import ModelMemoryBuffer, ModelMemoryBufferRegistry
from .storage.base import ModelMemoryStorage, ModelMemoryStorageRegistry
import ulid

class ModelMemoryAction:
    def __init__(
        self,
        config: ModelMemoryActionConfig,
        component_config: ModelMemoryComponentConfig,
        global_configs: ComponentGlobalConfigs,
    ):
        self.config: ModelMemoryActionConfig = config
        self.component_config: ModelMemoryComponentConfig = component_config
        self.global_configs: ComponentGlobalConfigs = global_configs

    async def run(self, context: ComponentActionContext, buffer: ModelMemoryBuffer, storage: ModelMemoryStorage) -> Any:
        result = await self._dispatch(context, buffer, storage)
        context.register_source("result", result)

        return (await context.render_variable(self.config.output, ignore_files=True)) if self.config.output else result

    async def _dispatch(self, context: ComponentActionContext, buffer: ModelMemoryBuffer, storage: ModelMemoryStorage) -> Any:
        session_id = await context.render_variable(self.config.session_id)

        if self.config.method == ModelMemoryActionMethod.LOAD:
            return await self._load(session_id, buffer, storage)

        if self.config.method == ModelMemoryActionMethod.APPEND:
            messages = await context.render_variable(self.config.messages)
            if messages is None:
                raise ValueError("messages is required for append")
            if not isinstance(messages, list):
                raise ValueError(f"messages must be a list after rendering, got {type(messages).__name__}")
            return await self._append(session_id, messages, buffer, context)

        if self.config.method == ModelMemoryActionMethod.SAVE:
            messages = (await context.render_variable(self.config.messages)) if self.config.messages is not None else None
            if messages is not None and not isinstance(messages, list):
                raise ValueError(f"messages must be a list after rendering, got {type(messages).__name__}")
            return await self._save(session_id, messages, buffer, storage, context)

        if self.config.method == ModelMemoryActionMethod.CLEAR:
            return await self._clear(session_id, buffer)

        if self.config.method == ModelMemoryActionMethod.DELETE:
            return await self._delete(session_id, buffer, storage)

        raise ValueError(f"Unsupported model memory action method: {self.config.method}")

    async def _load(self, session_id: str, buffer: ModelMemoryBuffer, storage: ModelMemoryStorage) -> dict:
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

        messages = self._flatten_turns(turns)

        if not self.component_config.window:
            if self.component_config.summary:
                return {
                    "summary": summary,
                    "messages": [],
                    "total_message_count": len(messages),
                    "window_message_count": 0,
                }

            return {
                "summary": summary,
                "messages": messages,
                "total_message_count": len(messages),
                "window_message_count": len(messages),
            }

        # window: return windowed messages
        recent_turns, _ = self._apply_window(turns, self.component_config.window)
        recent_messages = self._flatten_turns(recent_turns)

        return {
            "summary": summary,
            "messages": recent_messages,
            "total_message_count": len(messages),
            "window_message_count": len(recent_messages),
        }

    async def _append(self, session_id: str, messages: List[Any], buffer: ModelMemoryBuffer, context: ComponentActionContext) -> dict:
        turns = await buffer.get_turns(session_id)
        if turns is None:
            raise ValueError(f"Session not loaded: {session_id}. Call load before append.")

        await buffer.append_turn(session_id, messages)
        await self._prune_and_summarize(session_id, buffer, context)

        turns = await buffer.get_turns(session_id)
        return {"success": True, "buffer_turn_count": len(turns)}

    async def _save(self, session_id: str, messages: Optional[List[Any]], buffer: ModelMemoryBuffer, storage: ModelMemoryStorage, context: ComponentActionContext) -> dict:
        turns = await buffer.get_turns(session_id)

        if turns is None:
            # Implicit load -> append -> persist
            await self._load(session_id, buffer, storage)
            if messages is not None:
                await self._append(session_id, messages, buffer, context)
        elif messages is not None:
            await self._append(session_id, messages, buffer, context)

        turns = await buffer.get_turns(session_id)
        summary = await buffer.get_summary(session_id) or ""
        await storage.save(session_id, turns=turns, summary=summary)

        await buffer.merge_buffer(session_id)
        await buffer.take_snapshot(session_id)

        return {"success": True, "turn_count": len(turns)}

    async def _clear(self, session_id: str, buffer: ModelMemoryBuffer) -> dict:
        turns = await buffer.get_turns(session_id)
        if turns is not None:
            await buffer.restore_snapshot(session_id)
        return {"success": True}

    async def _delete(self, session_id: str, buffer: ModelMemoryBuffer, storage: ModelMemoryStorage) -> dict:
        await storage.delete(session_id)
        await buffer.remove(session_id)
        return {"success": True}

    # ── Window / Summary helpers ──

    async def _prune_and_summarize(self, session_id: str, buffer: ModelMemoryBuffer, context: ComponentActionContext) -> None:
        turns = await buffer.get_turns(session_id)

        if not self.component_config.window and not self.component_config.summary:
            return

        # summary-only: summarize everything, clear turns
        if not self.component_config.window and self.component_config.summary:
            if not turns:
                return
            summary = await buffer.get_summary(session_id) or ""
            new_summary = await self._invoke_summary(turns, summary, context)
            await buffer.set_turns(session_id, [])
            await buffer.set_summary(session_id, new_summary)
            return

        # window: prune excess turns
        recent_turns, older_turns = self._apply_window(turns, self.component_config.window)

        if not older_turns:
            return

        if self.component_config.summary:
            summary = await buffer.get_summary(session_id) or ""
            new_summary = await self._invoke_summary(older_turns, summary, context)
            await buffer.set_summary(session_id, new_summary)

        # Replace with windowed turns only
        await buffer.set_turns(session_id, recent_turns)

    def _apply_window(self, turns: List[List[Any]], window_config: Optional[ModelMemoryWindowConfig]):
        if not window_config:
            return turns, []
        if not window_config.max_turn_count and not window_config.max_message_count:
            return turns, []

        result = []
        turn_count = 0
        message_count = 0

        for turn in reversed(turns):
            if window_config.max_turn_count and turn_count >= window_config.max_turn_count:
                break
            if window_config.max_message_count and message_count + len(turn) > window_config.max_message_count:
                break
            result.insert(0, turn)
            turn_count += 1
            message_count += len(turn)

        # Always preserve at least the latest turn
        if not result and turns:
            result = [turns[-1]]

        older = turns[:len(turns) - len(result)]
        return result, older

    def _flatten_turns(self, turns: List[List[Any]]) -> List[Any]:
        return [ message for turn in turns for message in turn ]

    async def _invoke_summary(self, turns_to_summarize: List[List[Any]], previous_summary: str, context: ComponentActionContext) -> str:
        summary_config = self.component_config.summary
        if not summary_config:
            return previous_summary

        # Build messages for summary component
        instruction = summary_config.instruction
        messages_for_summary = []

        if instruction:
            messages_for_summary.append({"role": "system", "content": instruction})

        if previous_summary:
            messages_for_summary.append({"role": "system", "content": f"Previous summary: {previous_summary}"})

        for turn in turns_to_summarize:
            messages_for_summary.extend(turn)

        # Register sources for input mapping rendering
        context.register_source("messages", messages_for_summary)
        context.register_source("instruction", instruction)
        context.register_source("previous_summary", previous_summary)

        input_data = await context.render_variable(summary_config.input)

        # Resolve and invoke the summary component
        _, config = ComponentResolver(self.global_configs.components).resolve(summary_config.component)
        component = create_component(summary_config.component, config, self.global_configs, daemon=False)
        try:
            if not component.started:
                await component.start()

            response = await component.run(summary_config.action, ulid.ulid(), input_data)
        finally:
            await component.stop()

        # Extract string result
        if isinstance(response, dict):
            return response.get("content", response.get("text", str(response)))
        return str(response)


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
        self._buffer: ModelMemoryBuffer = self._create_buffer()
        self._storage: ModelMemoryStorage = self._create_storage()

    def _create_buffer(self) -> ModelMemoryBuffer:
        buffer_config = self.config.buffer
        driver = ModelMemoryBufferDriver(buffer_config.driver)

        if not ModelMemoryBufferRegistry:
            from . import buffer
        try:
            return ModelMemoryBufferRegistry[driver](buffer_config)
        except KeyError:
            raise ValueError(f"Unsupported model memory buffer driver: {driver}")

    def _create_storage(self) -> ModelMemoryStorage:
        storage_config = self.config.storage
        driver = ModelMemoryStorageDriver(storage_config.driver)

        if not ModelMemoryStorageRegistry:
            from . import storage
        try:
            return ModelMemoryStorageRegistry[driver](storage_config)
        except KeyError:
            raise ValueError(f"Unsupported model memory storage driver: {driver}")

    def _get_setup_requirements(self) -> Optional[List[str]]:
        reqs = []
        buffer_reqs = self._buffer.get_setup_requirements()
        if buffer_reqs:
            reqs.extend(buffer_reqs)
        storage_reqs = self._storage.get_setup_requirements()
        if storage_reqs:
            reqs.extend(storage_reqs)
        return reqs or None

    async def _serve(self) -> None:
        await self._buffer.setup()
        await self._storage.setup()

    async def _shutdown(self) -> None:
        await self._buffer.close()
        await self._storage.close()

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return await ModelMemoryAction(action, self.config, self.global_configs).run(context, self._buffer, self._storage)
