from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.compose import ComposeConfig
from mindor.core.controller import ControllerService, TaskState, TaskStatus, create_controller
from mindor.core.foundation.streaming.resources import StreamResource
from mindor.core.foundation.streaming.iterators import StreamIterator
import json

class ComposeManager:
    def __init__(self, config: ComposeConfig, daemon: bool):
        self.config: ComposeConfig = config
        self.controller: ControllerService = create_controller(
            self.config.controller,
            self.config.workflows,
            self.config.components,
            self.config.systems,
            self.config.listeners,
            self.config.gateways,
            self.config.tracers,
            self.config.loggers,
            daemon
        )

    async def launch_services(self, detach: bool, verbose: bool):
        await self.controller.launch_services(detach, verbose)

    async def terminate_services(self, verbose: bool):
        await self.controller.terminate_services(verbose)

    async def start_services(self, verbose: bool):
        await self.controller.start_services(verbose)

    async def stop_services(self, verbose: bool):
        await self.controller.stop_services(verbose)

    async def run_workflow(
        self,
        workflow_id: str,
        input: Dict[str, Any],
        output_path: Optional[str],
        verbose: bool,
        session_id: Optional[str] = None,
        metadata: Optional[Any] = None
    ) -> TaskState:
        if not self.controller.started:
            await self.controller.start()

        state = await self.controller.run_workflow(
            workflow_id,
            input,
            stop_at_streaming=True,
            session_id=session_id,
            metadata=metadata
        )

        if state.output is not None:
            state.output = self._render_output(state.output)

            if output_path:
                await self._save_output(state.output, output_path)
                state.output = None

        return state

    async def resume_workflow(
        self,
        task_id: str,
        job_id: str,
        run_id: Optional[str],
        answer: Any = None,
        output_path: Optional[str] = None,
    ) -> TaskState:
        state = await self.controller.resume_workflow(
            task_id,
            job_id,
            run_id,
            answer,
            wait_for_completion=True,
            stop_at_streaming=True,
        )

        if state.output is not None:
            state.output = self._render_output(state.output)

            if output_path:
                await self._save_output(state.output, output_path)
                state.output = None

        return state

    async def wait_for_completion(self, state: TaskState) -> TaskState:
        return await self.controller.wait_for_terminal_state(state.task_id)

    def _render_output(self, output: Any) -> AsyncIterator[Union[bytes, str]]:
        async def _render() -> AsyncIterator[Union[bytes, str]]:
            if isinstance(output, StreamResource):
                async for chunk in output:
                    yield chunk
            elif isinstance(output, StreamIterator):
                async for chunk in output:
                    if chunk is None:
                        continue
                    if isinstance(chunk, (bytes, str)):
                        yield chunk
                    else:
                        yield json.dumps(chunk, ensure_ascii=False, default=str)
            elif isinstance(output, (dict, list)):
                yield json.dumps(output, ensure_ascii=False, indent=2)
            else:
                yield str(output)

        return _render()

    async def _save_output(self, output: AsyncIterator[Union[bytes, str]], path: str) -> None:
        with open(path, "wb") as f:
            async for chunk in output:
                f.write(chunk if isinstance(chunk, bytes) else chunk.encode("utf-8"))
