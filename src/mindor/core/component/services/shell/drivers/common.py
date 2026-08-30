from __future__ import annotations

from typing import Optional, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import ShellActionConfig
from mindor.core.foundation.streaming.iterators import StreamChunkIterator, StreamIterator
from mindor.core.foundation.variable.array import ArrayValue
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from ..base import ComponentActionContext
from ....action.base import ComponentAction
import asyncio, os

class ShellAction(ComponentAction):
    def __init__(
        self,
        config: ShellActionConfig,
        base_dir: Optional[str],
        env: Optional[Dict[str, str]],
    ):
        self.config: ShellActionConfig = config
        self.base_dir: Optional[str] = base_dir
        self.env: Optional[Dict[str, str]] = env

    async def run(self, context: ComponentActionContext) -> Any:
        command    = await context.render_array(self.config.command)
        batch_size = await context.render_variable(self.config.batch_size)
        streaming  = await context.render_variable(self.config.streaming)

        params = await self._resolve_params(context)

        is_single_input  = not isinstance(command, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(command, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_commands in BatchSourceIterator(command, batch_size=batch_size or 1):
                    batch_results = await self._process_batch(batch_commands, params, streaming, context.cancellation_token)
                    for result in batch_results:
                        if streaming:
                            async def _stream_chunk_generator(result=result, scope=f"stream:{id(result)}"):
                                async for chunk in result:
                                    context.register_source("result[]", chunk, scope=scope)
                                    yield (await context.render_variable(self.config.output, scope=scope)) if not is_direct_output else chunk

                            yield StreamChunkIterator(_stream_chunk_generator(), is_fragmented=True)
                        else:
                            yield result

            return _stream_output_generator()
        else:
            results: List[Any] = []
            async for batch_commands in BatchSourceIterator(command, batch_size=batch_size or 1):
                batch_results = await self._process_batch(batch_commands, params, streaming, context.cancellation_token)
                for result in batch_results:
                    if streaming:
                        async def _stream_chunk_generator(result=result, scope=f"stream:{id(result)}"):
                            async for chunk in result:
                                context.register_source("result[]", chunk, scope=scope)
                                yield (await context.render_variable(self.config.output, scope=scope)) if not is_direct_output else chunk

                        results.append(StreamChunkIterator(_stream_chunk_generator(), is_fragmented=True))
                    else:
                        results.append(result)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not streaming and not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        working_dir = await self._resolve_working_directory()
        env         = await context.render_variable({ **(self.env or {}), **(self.config.env or {}) })
        timeout     = await context.render_scalar(self.config.timeout, "time") if self.config.timeout else None

        return {
            "working_dir": working_dir,
            "env":         env,
            "timeout":     timeout,
        }

    async def _resolve_working_directory(self) -> str:
        working_dir = self.config.working_dir

        if working_dir:
            working_dir = os.path.expanduser(working_dir)
            if self.base_dir:
                working_dir = os.path.abspath(os.path.join(self.base_dir, working_dir))
            else:
                working_dir = os.path.abspath(working_dir)
        else:
            working_dir = self.base_dir or os.getcwd()

        return working_dir

    async def _process_batch(
        self,
        commands: List[ArrayValue],
        params: Dict[str, Any],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Any]:
        return await asyncio.gather(*[
            self._process(command, params, streaming, cancellation_token) for command in commands
        ])

    async def _process(
        self,
        command: ArrayValue,
        params: Dict[str, Any],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Any:
        command = await command.collect()

        if streaming:
            return self._stream_command(command, params=params, cancellation_token=cancellation_token)

        return await self._run_command(command, params=params, cancellation_token=cancellation_token)

    @abstractmethod
    async def _run_command(
        self,
        command: List[str],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    def _stream_command(
        self,
        command: List[str],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> AsyncIterator[str]:
        pass
