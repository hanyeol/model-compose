from __future__ import annotations

from typing import Union, Optional, Dict, List, Tuple, Any
from dataclasses import dataclass, field
from mindor.dsl.schema.containers.docker import (
    DockerContainerConfig,
    DockerBuildConfig,
    DockerPortConfig,
    DockerVolumeConfig,
)
from mindor.core.logger import logging
from docker.models.containers import Container
from docker.types import Mount, DeviceRequest
from docker.errors import DockerException, NotFound
from pathlib import Path
import sys, asyncio, signal, time
import docker

class DockerPortsResolver:
    def __init__(self, ports: Optional[List[Union[str, int, DockerPortConfig]]]):
        self.ports: Optional[List[Union[str, int, DockerPortConfig]]] = ports

    def resolve(self) -> Dict[str, Union[str, Tuple[str, int]]]:
        """Normalize `ports` into docker-py's `containers.create(ports=...)` form:
        `{container_port/protocol: host_port}` for all-interface bind, or
        `{container_port/protocol: (host_ip, host_port)}` when a host IP is set."""
        ports: Dict[str, Union[str, Tuple[str, int]]] = {}

        for port in self.ports or []:
            if isinstance(port, int):
                ports[str(port)] = str(port)
                continue

            if isinstance(port, str):
                host_side, _, container_side = port.rpartition(":")
                host_ip, _, host_port = host_side.rpartition(":")
                if host_ip:
                    ports[container_side] = (host_ip, int(host_port))
                else:
                    ports[container_side] = host_port or container_side
                continue

            if isinstance(port, DockerPortConfig):
                if port.host_port is None:
                    continue
                key = f"{port.container_port}/{port.protocol}" if port.protocol else str(port.container_port)
                if port.host_ip:
                    ports[key] = (port.host_ip, port.host_port)
                else:
                    ports[key] = str(port.host_port)
                continue

        return ports

class DockerMountsResolver:
    def __init__(self, volumes: Optional[List[Union[str, DockerVolumeConfig]]]):
        self.volumes: Optional[List[Union[str, DockerVolumeConfig]]] = volumes

    def resolve(self) -> List[Mount]:
        return [ self._get_volume_mount(volume) for volume in self.volumes or [] ]

    def _get_volume_mount(self, volume: Union[str, DockerVolumeConfig]) -> Mount:
        if isinstance(volume, str):
            source, target, mode, *_ = volume.split(":") + [ None ]
            read_only = mode == "ro"

            return Mount(
                target=target,
                source=str(Path(source).resolve()),
                type="bind",
                read_only=read_only
            )

        if volume.type == "bind":
            return Mount(
                target=volume.target,
                source=str(Path(volume.source).resolve()),
                type="bind",
                read_only=volume.read_only or False
            )

        if volume.type == "volume":
            return Mount(
                target=volume.target,
                source=volume.source,
                type="volume",
                read_only=volume.read_only or False,
                no_copy=getattr(volume.volume, "nocopy", False),
                labels=getattr(volume.volume, "labels", None),
            )

        if volume.type == "tmpfs":
            return Mount(
                target=volume.target,
                source="",
                type="tmpfs",
                tmpfs_size=getattr(volume.tmpfs, "size", None),
                tmpfs_mode=getattr(volume.tmpfs, "mode", None),
            )

class DockerDeviceRequestsResolver:
    def __init__(self, gpus: Optional[Union[str, int]]):
        self.gpus: Optional[Union[str, int]] = gpus

    def resolve(self) -> Optional[List[DeviceRequest]]:
        if self.gpus is None:
            return None
        count = -1 if self.gpus == "all" else int(self.gpus)
        return [ DeviceRequest(count=count, capabilities=[["gpu"]]) ]

@dataclass
class DockerContainerParams:
    """Inputs for `DockerContainerRunner`. Mirrors `DockerContainerConfig`."""
    image: Optional[str] = None
    container_name: Optional[str] = None
    hostname: Optional[str] = None
    ports: Optional[List[Union[str, int, DockerPortConfig]]] = None
    networks: Optional[List[str]] = None
    extra_hosts: Optional[Dict[str, str]] = None
    volumes: Optional[List[Union[str, DockerVolumeConfig]]] = None
    environment: Optional[Dict[str, Union[str, int, float, bool]]] = None
    command: Optional[Union[str, List[str]]] = None
    entrypoint: Optional[Union[str, List[str]]] = None
    working_dir: Optional[str] = None
    user: Optional[str] = None
    gpus: Optional[Union[str, int]] = None
    shm_size: Optional[str] = None
    mem_limit: Optional[str] = None
    memswap_limit: Optional[str] = None
    cpu_shares: Optional[int] = None
    restart: str = "no"
    labels: Optional[Dict[str, str]] = None
    privileged: Optional[bool] = None
    security_opt: Optional[List[str]] = None
    build: Optional[DockerBuildConfig] = None

    @classmethod
    def from_config(cls, config: DockerContainerConfig) -> DockerContainerParams:
        """Build params from a DSL config. `image` / `container_name` are
        copied verbatim — if the config did not pin them, the caller is
        expected to assign manager-side decisions on the returned dataclass
        before constructing a `DockerContainerRunner`."""
        return cls(
            image=config.image,
            container_name=config.container_name,
            hostname=config.hostname,
            ports=config.ports,
            networks=config.networks,
            extra_hosts=config.extra_hosts,
            volumes=config.volumes,
            environment=config.environment,
            command=config.command,
            entrypoint=config.entrypoint,
            working_dir=config.working_dir,
            user=config.user,
            gpus=config.gpus,
            shm_size=config.shm_size,
            mem_limit=config.mem_limit,
            memswap_limit=config.memswap_limit,
            cpu_shares=config.cpu_shares,
            restart=config.restart,
            labels=config.labels,
            privileged=config.privileged,
            security_opt=config.security_opt,
            build=config.build,
        )

class DockerImageBuilder:
    """Builds, pulls, inspects, and removes Docker images. Stateless: each
    method takes a tag (and other inputs) explicitly."""
    def __init__(self, verbose: bool = False):
        self.verbose: bool = verbose

        self._client = docker.from_env()

    async def build(
        self,
        tag: str,
        *,
        path: Optional[str] = None,
        dockerfile: Optional[str] = None,
        build_args: Optional[Dict[str, Any]] = None,
        labels: Optional[Dict[str, str]] = None,
        target: Optional[str] = None,
        pull: Optional[bool] = None,
        cache_from: Optional[List[str]] = None,
        network_mode: Optional[str] = None,
    ) -> None:
        """Build a docker image from a disk-based build context at `path`.
        Knows nothing about mindor's image tiers — callers materialize the
        context themselves (e.g. via `archive_to_dir`) and pass the path."""
        try:
            response = self._client.api.build(
                path=path,
                dockerfile=dockerfile,
                tag=tag,
                buildargs=build_args or {},
                cache_from=cache_from or [],
                labels=labels or {},
                network_mode=network_mode,
                pull=pull,
                target=target,
                rm=True, forcerm=True, decode=True,
            )
            self._stream_build_output(response)
        except DockerException as e:
            raise RuntimeError(f"Failed to build image: {e}")

    async def pull(self, tag: str) -> None:
        try:
            self._client.images.pull(tag)
        except DockerException as e:
            raise RuntimeError(f"Failed to pull image: {e}")

    async def remove(self, tag: str, force: bool = False) -> None:
        try:
            self._client.images.remove(image=tag, force=force)
        except NotFound:
            pass
        except DockerException as e:
            raise RuntimeError(f"Failed to remove image: {e}")

    async def exists(self, tag: str) -> bool:
        try:
            return self._client.images.get(tag) is not None
        except NotFound:
            return False
        except DockerException as e:
            raise RuntimeError(f"Failed to check image: {e}")

    async def get_label(self, tag: str, label: str) -> Optional[str]:
        try:
            image = self._client.images.get(tag)
            return (image.labels or {}).get(label)
        except NotFound:
            return None
        except DockerException as e:
            raise RuntimeError(f"Failed to read image label: {e}")

    def _stream_build_output(self, response) -> None:
        for chunk in response:
            if "stream" in chunk:
                sys.stdout.write(chunk["stream"])
                sys.stdout.flush()
            elif "errorDetail" in chunk:
                raise RuntimeError(chunk["errorDetail"]["message"])

class DockerContainerRunner:
    """Lifecycle wrapper around a single Docker container.

    Pure lifecycle:
    - Creates the container from `DockerContainerParams` and starts it in
      detached or foreground mode.
    - On stop, requests a graceful stop via the daemon and tears the
      container down.

    Image build / pull / inspect lives in `DockerImageBuilder` — this class
    assumes the image already exists. Knows nothing about IPC protocols,
    codecs, or channels — callers that talk to a worker inside the container
    open their own transport (typically a docker attach socket).
    """
    def __init__(self, params: DockerContainerParams, verbose: bool = False):
        self.params: DockerContainerParams = params
        self.verbose: bool = verbose

        self._client = docker.from_env()
        self._shutdown_event: asyncio.Event = asyncio.Event()

    async def create(self, tty: bool = True, stdin_open: bool = True) -> None:
        try:
            try:
                self._client.containers.get(self.params.container_name)
            except NotFound:
                self._client.containers.create(
                    image=self.params.image,
                    name=self.params.container_name,
                    hostname=self.params.hostname,
                    environment=self.params.environment,
                    ports=DockerPortsResolver(self.params.ports).resolve(),
                    mounts=DockerMountsResolver(self.params.volumes).resolve(),
                    command=self.params.command,
                    entrypoint=self.params.entrypoint,
                    working_dir=self.params.working_dir,
                    user=self.params.user,
                    shm_size=self.params.shm_size,
                    mem_limit=self.params.mem_limit,
                    memswap_limit=self.params.memswap_limit,
                    cpu_shares=self.params.cpu_shares,
                    labels=self.params.labels,
                    network=self.params.networks[0] if self.params.networks else None,
                    privileged=self.params.privileged,
                    security_opt=self.params.security_opt,
                    restart_policy={ "Name": self.params.restart },
                    extra_hosts={ "host.docker.internal": "host-gateway", **(self.params.extra_hosts or {}) },
                    device_requests=DockerDeviceRequestsResolver(self.params.gpus).resolve(),
                    tty=tty, stdin_open=stdin_open, detach=True,
                )
        except DockerException as e:
            raise RuntimeError(f"Failed to create container: {e}")

    async def start(self, detach: bool) -> None:
        try:
            container = self._client.containers.get(self.params.container_name)
            container.start()

            if not detach:
                await self._run_foreground_container(container)
        except DockerException as e:
            raise RuntimeError(f"Failed to start container: {e}")

    async def stop(self, timeout: Optional[float] = None) -> None:
        try:
            container = self._client.containers.get(self.params.container_name)
            if timeout is not None:
                container.stop(timeout=int(timeout))
            else:
                container.stop()
        except NotFound:
            pass
        except DockerException as e:
            raise RuntimeError(f"Failed to stop container: {e}")

    async def remove(self, force: bool = False) -> None:
        try:
            container = self._client.containers.get(self.params.container_name)
            container.remove(force=force)
        except NotFound:
            pass
        except DockerException as e:
            raise RuntimeError(f"Failed to remove container: {e}")

    async def is_running(self) -> bool:
        try:
            container = self._client.containers.get(self.params.container_name)
            return container.status == "running"
        except NotFound:
            return False
        except DockerException as e:
            raise RuntimeError(f"Failed to check container: {e}")

    async def exists(self) -> bool:
        try:
            container = self._client.containers.get(self.params.container_name)
            return container is not None
        except NotFound:
            return False
        except DockerException as e:
            raise RuntimeError(f"Failed to check container: {e}")

    def get_container(self) -> Container:
        try:
            return self._client.containers.get(self.params.container_name)
        except NotFound:
            raise RuntimeError(f"Container '{self.params.container_name}' does not exist.")
        except DockerException as e:
            raise RuntimeError(f"Failed to get container: {e}")

    async def _run_foreground_container(self, container: Container) -> None:
        self._register_shutdown_signals()

        stream_logs_task       = asyncio.create_task(self._stream_container_logs(container))
        container_exit_waiter  = asyncio.create_task(self._wait_container_exit(container))
        shutdown_signal_waiter = asyncio.create_task(self._shutdown_event.wait())

        try:
            _, pending = await asyncio.wait(
                [ shutdown_signal_waiter, container_exit_waiter ],
                return_when=asyncio.FIRST_COMPLETED
            )

            if shutdown_signal_waiter.done():
                logging.info("Stopping container '%s' gracefully...", container.name)
                try:
                    container.stop(timeout=10)
                except DockerException:
                    pass

            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        finally:
            stream_logs_task.cancel()
            try:
                await stream_logs_task
            except asyncio.CancelledError:
                pass

    async def _wait_container_exit(self, container: Container) -> None:
        try:
            while not self._shutdown_event.is_set():
                container.reload()
                if container.status != "running":
                    exit_code = container.attrs.get("State", {}).get("ExitCode", 0)
                    logging.info("Container '%s' exited with exit code: %d", container.name, exit_code)
                    break
                await asyncio.sleep(0.5)
        except Exception as e:
            logging.error("Error while waiting for container '%s' to exit: %s", container.name, e)

    async def _stream_container_logs(self, container: Container) -> None:
        try:
            def _stream_logs_sync(container: Container) -> None:
                for line in container.logs(stream=True, follow=True, since=int(time.time())):
                    sys.stdout.buffer.write(line)
                    sys.stdout.flush()
            loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
            await loop.run_in_executor(None, _stream_logs_sync, container)
        except Exception as e:
            logging.error("Error while streaming logs from container '%s': %s", container.name, e)

    def _register_shutdown_signals(self) -> None:
        signal.signal(signal.SIGINT,  self._handle_shutdown_signal)
        signal.signal(signal.SIGTERM, self._handle_shutdown_signal)

    def _handle_shutdown_signal(self, signum, frame) -> None:
        self._shutdown_event.set()
