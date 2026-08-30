from typing import Optional, Dict, List, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import SshShellComponentConfig
from mindor.dsl.schema.action import SshShellActionConfig
from mindor.dsl.schema.transport.ssh import SshAuthType, SshConnectionConfig
from mindor.core.foundation.variable.time import parse_time
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.transport.ssh_client import (
    SshAuthParams,
    SshClient,
    SshConnectionParams,
    SshKeyfileAuthParams,
    SshPasswordAuthParams,
)
from mindor.core.logger import logging
from ..base import ShellService, ShellDriver, register_shell_service
from ..base import ComponentActionContext
from .common import ShellAction

class SshShellAction(ShellAction):
    def __init__(
        self,
        config: SshShellActionConfig,
        base_dir: Optional[str],
        env: Optional[Dict[str, str]],
        client: SshClient,
    ):
        super().__init__(config, base_dir, env)

        self.client: SshClient = client

    async def _resolve_working_directory(self) -> str:
        # Remote paths are interpreted by the login shell; no local expansion.
        working_dir = self.config.working_dir

        if working_dir and self.base_dir and not working_dir.startswith("/"):
            return f"{self.base_dir.rstrip('/')}/{working_dir}"

        return working_dir or self.base_dir or ""

    async def _run_command(
        self,
        command: List[str],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> Dict[str, Any]:
        working_dir = params["working_dir"]

        logging.debug("[shell] Running remote command: %s (cwd: %s)", " ".join(command), working_dir)

        stdout, stderr, exit_code = await self.client.run_command(
            command,
            working_dir=working_dir or None,
            env=params["env"],
            timeout=params["timeout"],
        )

        logging.debug("[shell] Remote command exited with code %d", exit_code)

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
        working_dir = params["working_dir"]

        logging.debug("[shell] Streaming remote command: %s (cwd: %s)", " ".join(command), working_dir)

        async for line in self.client.stream_command(
            command,
            working_dir=working_dir or None,
            env=params["env"],
            timeout=params["timeout"],
        ):
            yield line

@register_shell_service(ShellDriver.SSH)
class SshShellService(ShellService):
    config: SshShellComponentConfig

    def __init__(self, id: str, config: SshShellComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.client: Optional[SshClient] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "paramiko" ]

    async def _setup(self) -> None:
        if self.config.manage.scripts.install:
            async with self._create_client() as client:
                for command in self.config.manage.scripts.install:
                    await client.run_command(command, self.config.manage.working_dir, self.config.manage.env)

    async def _teardown(self) -> None:
        if self.config.manage.scripts.clean:
            async with self._create_client() as client:
                for command in self.config.manage.scripts.clean:
                    await client.run_command(command, self.config.manage.working_dir, self.config.manage.env)

    async def _start(self) -> None:
        self.client = self._create_client()
        await self.client.connect()

        await super()._start()

    async def _stop(self) -> None:
        await super()._stop()

        if self.client is not None:
            try:
                await self.client.close()
            finally:
                self.client = None

    async def _run(self, action: SshShellActionConfig, context: ComponentActionContext) -> Any:
        return await SshShellAction(action, self.config.base_dir, self.config.env, self.client).run(context)

    def _create_client(self) -> SshClient:
        return SshClient(self._build_connection_params(self.config.connection))

    def _build_connection_params(self, config: SshConnectionConfig) -> SshConnectionParams:
        return SshConnectionParams(
            host=config.host,
            port=config.port,
            auth=self._build_auth_params(config.auth),
            keepalive_interval=int(parse_time(config.keepalive_interval)),
        )

    def _build_auth_params(self, config) -> SshAuthParams:
        if config.type == SshAuthType.KEYFILE:
            return SshKeyfileAuthParams(
                username=config.username,
                keyfile=config.keyfile,
                passphrase=config.passphrase,
            )

        if config.type == SshAuthType.PASSWORD:
            return SshPasswordAuthParams(
                username=config.username,
                password=config.password,
            )

        raise ValueError(f"Unsupported SSH auth type: {config.type}")
