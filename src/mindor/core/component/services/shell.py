from typing import Optional, Dict, List, Any
from collections.abc import AsyncIterable, AsyncIterator
from mindor.dsl.schema.component import ShellComponentConfig
from mindor.dsl.schema.action import ActionConfig, ShellActionConfig
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.foundation.streaming.iterators import StreamChunkIterator
from mindor.core.foundation.variable.array import ArrayValue
from mindor.core.utils.shell import run_command_foreground, run_command
from mindor.core.foundation.variable.time import parse_duration
from mindor.core.logger import logging
from ..base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ..context import ComponentActionContext
import asyncio, os

class ShellAction:
    def __init__(
        self,
        config: ShellActionConfig,
        base_dir: Optional[str],
        env: Optional[Dict[str, str]]
    ):
        self.config: ShellActionConfig = config
        self.base_dir: Optional[str] = base_dir
        self.env: Optional[Dict[str, str]] = env

    async def run(self, context: ComponentActionContext) -> Any:
        command    = await context.render_array(self.config.command)
        batch_size = await context.render_variable(self.config.batch_size)
        streaming  = await context.render_variable(self.config.streaming)

        params = await self._resolve_params(context)

        is_single_input  = not isinstance(command, (list, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(command, AsyncIterator):
            async def _stream_output_generator():
                async for batch_commands in BatchSourceIterator(command, batch_size=batch_size or 1):
                    batch_results = await self._process_batch(batch_commands, params, streaming)
                    for result in batch_results:
                        if isinstance(result, AsyncIterable):
                            async def _stream_chunk_generator(result=result, scope=f"stream:{id(result)}"):
                                async for chunk in result:
                                    context.register_source("result[]", chunk, scope=scope)
                                    yield (await context.render_variable(self.config.output, scope=scope)) if not is_direct_output else chunk

                            yield StreamChunkIterator(_stream_chunk_generator(), is_fragmented=False)
                        else:
                            yield result

            return _stream_output_generator()
        else:
            results: List[Any] = []
            async for batch_commands in BatchSourceIterator(command, batch_size=batch_size or 1):
                batch_results = await self._process_batch(batch_commands, params, streaming)
                for result in batch_results:
                    if isinstance(result, AsyncIterable):
                        async def _stream_chunk_generator(result=result, scope=f"stream:{id(result)}"):
                            async for chunk in result:
                                context.register_source("result[]", chunk, scope=scope)
                                yield (await context.render_variable(self.config.output, scope=scope)) if not is_direct_output else chunk

                        results.append(StreamChunkIterator(_stream_chunk_generator(), is_fragmented=False))
                    else:
                        results.append(result)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        working_dir = await self._resolve_working_directory()
        env         = await context.render_variable({ **(self.env or {}), **(self.config.env or {}) })
        timeout     = parse_duration(await context.render_variable(self.config.timeout)) if self.config.timeout else None

        return {
            "working_dir": working_dir,
            "env":         env,
            "timeout":     timeout,
        }

    async def _process_batch(
        self,
        commands: List[ArrayValue],
        params: Dict[str, Any],
        streaming: bool,
    ) -> List[Any]:
        return await asyncio.gather(*[
            self._process(command, params, streaming) for command in commands
        ])

    async def _process(self, command: ArrayValue, params: Dict[str, Any], streaming: bool) -> Any:
        if streaming:
            return self._stream_command(command.values, params["working_dir"], params["env"], params["timeout"])

        return await self._run_command(command.values, params["working_dir"], params["env"], params["timeout"])

    async def _run_command(
        self,
        command: List[str],
        working_dir: str,
        env: Dict[str, str],
        timeout: Optional[float]
    ) -> Dict[str, Any]:
        logging.debug("[shell] Running command: %s (cwd: %s)", " ".join(command), working_dir)
        stdout, stderr, exit_code = await run_command(command, working_dir, env, timeout)
        logging.debug("[shell] Command exited with code %d", exit_code)

        return {
            "stdout": stdout.decode().strip(),
            "stderr": stderr.decode().strip(),
            "exit_code": exit_code
        }

    async def _stream_command(
        self,
        command: List[str],
        working_dir: str,
        env: Dict[str, str],
        timeout: Optional[float]
    ):
        """Yield stdout lines as they are produced by the process."""
        logging.debug("[shell] Streaming command: %s (cwd: %s)", " ".join(command), working_dir)

        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=working_dir,
            env={ **os.environ, **(env or {}) },
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        async def _readlines():
            assert process.stdout is not None
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                yield line.decode(errors="replace").rstrip("\n")

        try:
            if timeout is not None:
                async def _drain_with_timeout():
                    async for line in _readlines():
                        yield line
                    await process.wait()

                gen = _drain_with_timeout()
                while True:
                    try:
                        line = await asyncio.wait_for(gen.__anext__(), timeout=timeout)
                    except StopAsyncIteration:
                        break
                    except asyncio.TimeoutError:
                        process.kill()
                        await process.wait()
                        raise TimeoutError(f"Command timed out: {' '.join(command)}")
                    yield line
            else:
                async for line in _readlines():
                    yield line
                await process.wait()

            logging.debug("[shell] Streaming command exited with code %d", process.returncode)
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()

    async def _resolve_working_directory(self) -> str:
        working_dir = self.config.working_dir

        if working_dir:
            if self.base_dir:
                working_dir = os.path.abspath(os.path.join(self.base_dir, working_dir))
            else:
                working_dir = os.path.abspath(working_dir)
        else:
            working_dir = self.base_dir or os.getcwd()

        return working_dir

@register_component(ComponentType.SHELL)
class ShellComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: ShellComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

    async def _setup(self) -> None:
        if self.config.manage.scripts.install:
            for command in self.config.manage.scripts.install:
                await run_command_foreground(command, self.config.manage.working_dir, self.config.manage.env)

    async def _teardown(self):
        if self.config.manage.scripts.clean:
            for command in self.config.manage.scripts.clean:
                await run_command_foreground(command, self.config.manage.working_dir, self.config.manage.env)

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return await ShellAction(action, self.config.base_dir, self.config.env).run(context)
