from typing import Optional, Dict, List, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import LocalShellComponentConfig
from mindor.dsl.schema.action import LocalShellActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.shell import run_command_foreground, run_command, stream_subprocess
from mindor.core.logger import logging
from ..base import ShellService, ShellDriver, register_shell_service
from ..base import ComponentActionContext
from .common import ShellAction
import asyncio

class LocalShellAction(ShellAction):
    async def _run_command(
        self,
        command: List[str],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> Dict[str, Any]:
        working_dir = params["working_dir"]

        logging.debug("[shell] Running command: %s (cwd: %s)", " ".join(command), working_dir)

        stdout, stderr, exit_code = await run_command(
            command,
            working_dir=working_dir,
            env=params["env"],
            timeout=params["timeout"],
        )

        logging.debug("[shell] Command exited with code %d", exit_code)

        return {
            "stdout": stdout.decode().strip(),
            "stderr": stderr.decode().strip(),
            "exit_code": exit_code,
        }

    async def _stream_command(
        self,
        command: List[str],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> AsyncIterator[str]:
        """Yield stdout lines as they are produced by the process."""
        working_dir = params["working_dir"]
        timeout = params["timeout"]

        logging.debug("[shell] Streaming command: %s (cwd: %s)", " ".join(command), working_dir)

        async def _handle_stdout(stdout: asyncio.StreamReader) -> AsyncIterator[str]:
            while True:
                line = await stdout.readline()
                if not line:
                    return
                yield line.decode(errors="replace")

        async with stream_subprocess(
            command,
            stdout_handler=_handle_stdout,
            working_dir=working_dir,
            env=params["env"],
        ) as (process, stdout_iterator, _):
            if timeout is not None:
                while True:
                    try:
                        line = await asyncio.wait_for(stdout_iterator.__anext__(), timeout=timeout)
                    except StopAsyncIteration:
                        break
                    except asyncio.TimeoutError:
                        raise TimeoutError(f"Command timed out: {' '.join(command)}")
                    yield line
            else:
                async for line in stdout_iterator:
                    yield line

            await process.wait()

            logging.debug("[shell] Streaming command exited with code %d", process.returncode)

@register_shell_service(ShellDriver.LOCAL)
class LocalShellService(ShellService):
    def __init__(self, id: str, config: LocalShellComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _setup(self) -> None:
        if self.config.manage.scripts.install:
            for command in self.config.manage.scripts.install:
                await run_command_foreground(command, self.config.manage.working_dir, self.config.manage.env)

    async def _teardown(self) -> None:
        if self.config.manage.scripts.clean:
            for command in self.config.manage.scripts.clean:
                await run_command_foreground(command, self.config.manage.working_dir, self.config.manage.env)

    async def _run(self, action: LocalShellActionConfig, context: ComponentActionContext) -> Any:
        return await LocalShellAction(action, self.config.base_dir, self.config.env).run(context)
