from typing import Optional, Dict, List, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import LocalShellComponentConfig
from mindor.dsl.schema.action import LocalShellActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.shell import run_command_foreground, run_subprocess, stream_subprocess
from mindor.core.logger import logging
from ..base import ShellDriver, ShellDriverType, register_shell_driver
from ..base import ComponentActionContext
from .common import ShellAction
import asyncio, os

class LocalShellAction(ShellAction):
    async def _run_command(
        self,
        command: List[str],
        *,
        stdin: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> Dict[str, Any]:
        stdin = self._as_stdin_stream(stdin) if stdin is not None else None

        logging.debug("[shell] Running command: %s (cwd: %s)", " ".join(command), params["working_dir"])

        try:
            process, stdout, stderr = await asyncio.wait_for(
                run_subprocess(
                    command,
                    stdin=stdin,
                    stdout_handler=lambda stream: stream.read(),
                    stderr_handler=lambda stream: stream.read(),
                    working_dir=params["working_dir"],
                    env=params["env"],
                ),
                timeout=params["timeout"],
            )
        except asyncio.TimeoutError:
            raise TimeoutError(f"Command timed out: {' '.join(command)}")

        exit_code = process.returncode

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
        stdin: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> AsyncIterator[str]:
        stdin = self._as_stdin_stream(stdin) if stdin is not None else None

        logging.debug("[shell] Streaming command: %s (cwd: %s)", " ".join(command), params["working_dir"])

        async def _handle_stdout(stdout: asyncio.StreamReader) -> AsyncIterator[str]:
            while True:
                line = await stdout.readline()
                if not line:
                    return
                yield line.decode(errors="replace")

        async with stream_subprocess(
            command,
            stdin=stdin,
            stdout_handler=_handle_stdout,
            working_dir=params["working_dir"],
            env=params["env"],
        ) as (process, stdout_iterator, _):
            while True:
                try:
                    line = await asyncio.wait_for(stdout_iterator.__anext__(), timeout=params["timeout"])
                except StopAsyncIteration:
                    break
                except asyncio.TimeoutError:
                    raise TimeoutError(f"Command timed out: {' '.join(command)}")
                yield line

            await process.wait()

            logging.debug("[shell] Streaming command exited with code %d", process.returncode)

    def _resolve_working_directory(self, working_dir: Optional[str]) -> str:
        if working_dir:
            working_dir = os.path.expanduser(working_dir)

            if self.base_dir:
                return os.path.abspath(os.path.join(self.base_dir, working_dir))

            return os.path.abspath(working_dir)

        return self.base_dir or os.getcwd()

@register_shell_driver(ShellDriverType.LOCAL)
class LocalShellService(ShellDriver):
    def __init__(self, id: str, config: LocalShellComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _setup(self) -> None:
        if self.config.manage.scripts.install:
            for command in self.config.manage.scripts.install:
                await run_command_foreground(
                    command,
                    working_dir=self.config.manage.working_dir,
                    env=self.config.manage.env,
                )

    async def _teardown(self) -> None:
        if self.config.manage.scripts.clean:
            for command in self.config.manage.scripts.clean:
                await run_command_foreground(
                    command,
                    working_dir=self.config.manage.working_dir,
                    env=self.config.manage.env,
                )

    async def _run(self, action: LocalShellActionConfig, context: ComponentActionContext) -> Any:
        return await LocalShellAction(action, self.config.base_dir, self.config.env).run(context)
