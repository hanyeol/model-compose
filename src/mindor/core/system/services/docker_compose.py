from typing import Optional, List
from mindor.dsl.schema.system.impl.docker_compose import DockerComposeSystemConfig
from mindor.dsl.schema.system.impl.types import SystemType
from mindor.core.system.base import SystemService, register_system
from mindor.core.logger import logging
from mindor.core.utils.time import parse_duration
import asyncio
import shutil

@register_system(SystemType.DOCKER_COMPOSE)
class DockerComposeSystem(SystemService):
    def __init__(self, id: str, config: DockerComposeSystemConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.config: DockerComposeSystemConfig = config

    async def _setup(self) -> None:
        if not shutil.which("docker"):
            raise RuntimeError("'docker' command not found. Please install Docker to use docker-compose systems.")

    async def _serve(self) -> None:
        command = self._build_up_command()
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error = stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"Docker compose up failed (exit {process.returncode}): {error}")

        logging.info(f"Docker compose started: {' '.join(self.config.files) or 'docker-compose.yml'}")

    async def _shutdown(self) -> None:
        command = self._build_down_command()
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error = stderr.decode("utf-8", errors="replace").strip()
            logging.warning(f"Docker compose down failed (exit {process.returncode}): {error}")
        else:
            logging.info(f"Docker compose stopped: {' '.join(self.config.files) or 'docker-compose.yml'}")

    async def _is_ready(self) -> bool:
        command = self._build_base_command() + [ "ps", "--format", "json", "--status", "running" ]

        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()
        return process.returncode == 0 and len(stdout.strip()) > 0

    def _build_base_command(self) -> List[str]:
        command = [ "docker", "compose" ]

        if self.config.project_name:
            command += ["-p", self.config.project_name]

        for f in self.config.files:
            command += [ "-f", f ]

        if self.config.env_file:
            command += [ "--env-file", self.config.env_file ]

        if self.config.profiles:
            for profile in self.config.profiles:
                command += [ "--profile", profile ]

        return command

    def _build_up_command(self) -> List[str]:
        command = self._build_base_command() + [ "up", "-d" ]

        if self.config.build:
            command.append("--build")

        if self.config.wait:
            command.append("--wait")
            if self.config.wait_timeout:
                timeout_seconds = int(parse_duration(self.config.wait_timeout).total_seconds())
                command += ["--wait-timeout", str(timeout_seconds)]

        return command

    def _build_down_command(self) -> List[str]:
        return self._build_base_command() + [ "down" ]
