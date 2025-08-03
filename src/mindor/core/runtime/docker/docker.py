from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.runtime import DockerRuntimeConfig, DockerBuildConfig, DockerPortConfig, DockerVolumeConfig, DockerHealthCheck
from mindor.core.logger import logging
from docker.models.containers import Container
from docker.types import Mount, DeviceRequest
from docker.errors import DockerException, NotFound
import docker, sys, asyncio, signal, time

class DockerPortsResolver:
    def __init__(self, ports: Optional[List[Union[str, int, DockerPortConfig]]]):
        self.ports: Optional[List[Union[str, int, DockerPortConfig]]] = ports

    def resolve(self) -> Dict[str, str]:
        ports: Dict[str, str] = {}

        for port in self.ports or []:
            if isinstance(port, int):
                ports[str(port)] = str(port)
                continue

            if isinstance(port, str):
                target, published = port.split(":")
                ports[str(target)] = str(published)
                continue

            if isinstance(port, DockerPortConfig):
                if port.published is not None:
                    ports[str(port.target)] = str(port.published)
                continue

        return ports

class DockerMountsResolver:
    def __init__(self, volumes: Optional[List[Union[str, DockerVolumeConfig]]]):
        self.volumes: Optional[List[Union[str, DockerVolumeConfig]]] = volumes

    def resolve(self) -> List[Mount]:
        mounts: List[Mount] = []

        for volume in self.volumes or []:
            if isinstance(volume, str):
                source, target = volume.split(":")
                mounts.append(Mount(target=target, source=source, type="bind"))
                continue

            if isinstance(volume, DockerVolumeConfig) and volume.type == "bind":
                mounts.append(self._get_volume_mount(volume))
                continue

        return mounts
    
    def _get_volume_mount(self, volume: DockerVolumeConfig) -> Mount:
        if volume.type == "bind":
            return Mount(
                target=volume.target,
                source=volume.source,
                type="bind",
                read_only=volume.read_only or False
            )
        
        if volume.type == "volume":
            return Mount(
                target=volume.target,
                source=volume.source,
                type="volume",
                read_only=volume.read_only or False,
                volume_options=volume.volume or {}
            )
        
        if volume.type == "tmpfs":
            return Mount(
                target=volume.target,
                type="tmpfs",
                tmpfs_options=volume.tmpfs or {}
            )

class DockerRuntimeManager:
    def __init__(self, config: DockerRuntimeConfig, verbose: bool):
        self.config: DockerRuntimeConfig = config
        self.verbose: bool = verbose
        self.client = docker.from_env()
        self._shutdown_event: asyncio.Event = asyncio.Event()

    async def start_container(self, detach: bool) -> None:
        try:
            try:
                container = self.client.containers.get(self.config.container_name)
            except NotFound:
                container = self.client.containers.create(
                    image=self.config.image,
                    name=self.config.container_name,
                    hostname=self.config.hostname,
                    environment=self.config.environment,
                    ports=DockerPortsResolver(self.config.ports).resolve(),
                    mounts=DockerMountsResolver(self.config.volumes).resolve(),
                    command=self.config.command,
                    entrypoint=self.config.entrypoint,
                    working_dir=self.config.working_dir,
                    user=self.config.user,
                    mem_limit=self.config.mem_limit,
                    memswap_limit=self.config.memswap_limit,
                    cpu_shares=self.config.cpu_shares,
                    labels=self.config.labels,
                    network=self.config.networks[0] if self.config.networks else None,
                    privileged=self.config.privileged,
                    security_opt=self.config.security_opt,
                    restart_policy={ "Name": self.config.restart },
                    tty=True, stdin_open=True, detach=True
                )
            container.start()

            if not detach:
                await self._run_foreground_container(container)
        except DockerException as e:
            raise RuntimeError(f"Failed to start container: {e}")

    async def stop_container(self) -> None:
        try:
            container = self.client.containers.get(self.config.container_name)
            container.stop()
        except NotFound:
            pass
        except DockerException as e:
            raise RuntimeError(f"Failed to stop container: {e}")

    async def remove_container(self, force: bool = False) -> None:
        try:
            container = self.client.containers.get(self.config.container_name)
            container.remove(force=force)
        except NotFound:
            pass
        except DockerException as e:
            raise RuntimeError(f"Failed to remove container: {e}")

    async def is_container_running(self) -> bool:
        try:
            container = self.client.containers.get(self.config.container_name)
            return container.status == "running"
        except NotFound:
            return False
        except DockerException as e:
            raise RuntimeError(f"Failed to check container: {e}")

    async def exists_container(self) -> bool:
        try:
            return True if self.client.containers.get(self.config.container_name) else False
        except NotFound:
            return False
        except DockerException as e:
            raise RuntimeError(f"Failed to check container: {e}")

    async def build_image(self) -> None:
        try:
            response = self.client.api.build(
                path=self.config.build.context,
                dockerfile=self.config.build.dockerfile,
                tag=self.config.image,
                buildargs=self.config.build.args or {},
                target=self.config.build.target,
                cache_from=self.config.build.cache_from or [],
                labels=self.config.build.labels or {},
                network_mode=self.config.build.network,
                pull=self.config.build.pull,
                rm=True, forcerm=True, decode=True
            )

            for chunk in response:
                if "stream" in chunk:
                    sys.stdout.write(chunk["stream"])
                    sys.stdout.flush()
                elif "errorDetail" in chunk:
                    raise RuntimeError(chunk["errorDetail"]["message"])
        except DockerException as e:
            raise RuntimeError(f"Failed to build image: {e}")

    async def pull_image(self) -> None:
        try:
            self.client.images.pull(self.config.image)
        except DockerException as e:
            raise RuntimeError(f"Failed to pull image: {e}")

    async def remove_image(self, force: bool = False) -> None:
        try:
            self.client.images.remove(image=self.config.image, force=force)
        except NotFound:
            pass
        except DockerException as e:
            raise RuntimeError(f"Failed to remove image: {e}")

    async def exists_image(self) -> bool:
        try:
            return True if self.client.images.get(self.config.image or "") else False
        except NotFound:
            return False
        except DockerException as e:
            raise RuntimeError(f"Failed to check image: {e}")

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
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, _stream_logs_sync, container)
        except Exception as e:
            logging.error("Error while streaming logs from container '%s': %s", container.name, e)

    def _register_shutdown_signals(self) -> None:
        signal.signal(signal.SIGINT,  self._handle_shutdown_signal)
        signal.signal(signal.SIGTERM, self._handle_shutdown_signal)

    def _handle_shutdown_signal(self, signum, frame) -> None:
        self._shutdown_event.set()
