from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.runtime import AppleContainerRuntimeConfig, AppleContainerBuildConfig, AppleContainerVolumeConfig
from mindor.core.logger import logging
import sys, asyncio, signal

class AppleContainerPortsResolver:
    def __init__(self, ports: Optional[List[Union[str, int]]]):
        self.ports: Optional[List[Union[str, int]]] = ports

    def resolve(self) -> List[str]:
        args: List[str] = []
        for port in self.ports or []:
            if isinstance(port, int):
                args.extend([ "-p", f"{port}:{port}" ])
                continue
            if isinstance(port, str):
                args.extend([ "-p", port ])
                continue
        return args

class AppleContainerMountsResolver:
    def __init__(self, volumes: Optional[List[Union[str, AppleContainerVolumeConfig]]]):
        self.volumes: Optional[List[Union[str, AppleContainerVolumeConfig]]] = volumes

    def resolve(self) -> List[str]:
        args: List[str] = []
        for volume in self.volumes or []:
            if isinstance(volume, str):
                args.extend([ "--volume", volume ])
                continue
            if isinstance(volume, AppleContainerVolumeConfig):
                mount_str = f"{volume.name}:{volume.target}"
                args.extend([ "--volume", mount_str ])
                continue
        return args

class AppleContainerRuntimeManager:
    def __init__(self, config: AppleContainerRuntimeConfig, verbose: bool):
        self.config: AppleContainerRuntimeConfig = config
        self.verbose: bool = verbose
        self._shutdown_event: asyncio.Event = asyncio.Event()

    # ===== Container Lifecycle =====

    async def start_container(self, detach: bool) -> None:
        args = ["run"]

        if self.config.container_name:
            args.extend(["--name", self.config.container_name])

        if detach:
            args.append("-d")

        args.extend(AppleContainerPortsResolver(self.config.ports).resolve())
        args.extend(AppleContainerMountsResolver(self.config.volumes).resolve())

        for key, value in (self.config.environment or {}).items():
            args.extend(["-e", f"{key}={value}"])

        if self.config.cpus is not None:
            args.extend(["--cpus", str(self.config.cpus)])
        if self.config.mem_limit is not None:
            args.extend(["--memory", self.config.mem_limit])

        args.append(self.config.image)

        if self.config.command:
            if isinstance(self.config.command, str):
                args.append(self.config.command)
            else:
                args.extend(self.config.command)

        await self._run_command(args, capture_output=detach)

        if not detach:
            await self._run_foreground_container()

    async def stop_container(self) -> None:
        try:
            await self._run_command(["stop", self.config.container_name])
        except RuntimeError as e:
            logging.warning("Failed to stop container '%s': %s", self.config.container_name, e)

    async def remove_container(self, force: bool = False) -> None:
        args = ["rm"]
        if force:
            args.append("-f")
        args.append(self.config.container_name)

        try:
            await self._run_command(args)
        except RuntimeError:
            pass

    async def is_container_running(self) -> bool:
        try:
            process = await self._run_command(["ls"], check=False)
            stdout, _ = await process.communicate()
            return self.config.container_name in stdout.decode()
        except Exception:
            return False

    async def exists_container(self) -> bool:
        try:
            process = await self._run_command(["ls"], check=False)
            stdout, _ = await process.communicate()
            return self.config.container_name in stdout.decode()
        except Exception:
            return False

    # ===== Image Management =====

    async def build_image(self) -> None:
        if not self.config.build:
            raise RuntimeError("Build configuration is required")

        args = ["build"]

        if self.config.image:
            args.extend(["-t", self.config.image])

        if self.config.build.dockerfile:
            args.extend(["-f", self.config.build.dockerfile])

        for key, value in (self.config.build.args or {}).items():
            args.extend(["--build-arg", f"{key}={value}"])

        args.append(self.config.build.context or ".")

        await self._run_command(args, capture_output=False)

    async def pull_image(self) -> None:
        await self._run_command(["image", "pull", self.config.image], capture_output=False)

    async def remove_image(self, force: bool = False) -> None:
        try:
            await self._run_command(["image", "rm", self.config.image])
        except RuntimeError:
            pass

    async def exists_image(self) -> bool:
        try:
            process = await self._run_command(["image", "ls"], check=False)
            stdout, _ = await process.communicate()
            return self.config.image in stdout.decode()
        except Exception:
            return False

    # ===== DNS Management =====

    async def setup_dns(self) -> None:
        if not self.config.dns:
            return

        try:
            await self._run_command(
                ["system", "dns", "create", self.config.dns.domain]
            )
            logging.info(
                "DNS domain '%s' created. Container accessible at: %s.%s",
                self.config.dns.domain,
                self.config.dns.hostname or self.config.container_name,
                self.config.dns.domain
            )
        except RuntimeError as e:
            logging.warning("Failed to setup DNS: %s", e)

    # ===== Volume Management =====

    async def create_volumes(self) -> None:
        for volume in self.config.volumes or []:
            if isinstance(volume, AppleContainerVolumeConfig):
                try:
                    await self._run_command(["volume", "create", volume.name])
                except RuntimeError:
                    pass  # may already exist

    # ===== Private Helpers =====

    async def _run_command(
        self,
        args: List[str],
        check: bool = True,
        capture_output: bool = True
    ) -> asyncio.subprocess.Process:
        command = ["container"] + args

        logging.debug("Running: %s", " ".join(command))

        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE if capture_output else sys.stdout,
            stderr=asyncio.subprocess.PIPE if capture_output else sys.stderr
        )

        if check:
            stdout, stderr = await process.communicate()
            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                raise RuntimeError(
                    f"Command '{' '.join(command)}' failed (exit {process.returncode}): {error_msg}"
                )

        return process

    async def _run_foreground_container(self) -> None:
        self._register_shutdown_signals()

        await self._shutdown_event.wait()

        logging.info(
            "Stopping container '%s' gracefully...",
            self.config.container_name
        )
        await self.stop_container()

    def _register_shutdown_signals(self) -> None:
        signal.signal(signal.SIGINT,  self._handle_shutdown_signal)
        signal.signal(signal.SIGTERM, self._handle_shutdown_signal)

    def _handle_shutdown_signal(self, signum, frame) -> None:
        self._shutdown_event.set()
