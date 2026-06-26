from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.runtime import DockerRuntimeConfig, DockerBuildConfig, DockerPortConfig, DockerVolumeConfig, DockerHealthCheck
from mindor.core.logger import logging
from docker.models.containers import Container
from docker.types import Mount, DeviceRequest
from docker.errors import DockerException, NotFound
from pathlib import Path
import docker, sys, asyncio, signal, time, io, tarfile

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
                published, target = port.split(":")
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

class DockerRuntimeManager:
    def __init__(self, config: DockerRuntimeConfig, verbose: bool):
        self.config: DockerRuntimeConfig = config
        self.verbose: bool = verbose
        self.client = docker.from_env()
        self._shutdown_event: asyncio.Event = asyncio.Event()

    async def create_container(self) -> None:
        try:
            try:
                self.client.containers.get(self.config.container_name)
            except NotFound:
                self.client.containers.create(
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
                    shm_size=self.config.shm_size,
                    mem_limit=self.config.mem_limit,
                    memswap_limit=self.config.memswap_limit,
                    cpu_shares=self.config.cpu_shares,
                    labels=self.config.labels,
                    network=self.config.networks[0] if self.config.networks else None,
                    privileged=self.config.privileged,
                    security_opt=self.config.security_opt,
                    restart_policy={ "Name": self.config.restart },
                    extra_hosts=self.config.extra_hosts,
                    device_requests=DockerDeviceRequestsResolver(self.config.gpus).resolve(),
                    tty=True, stdin_open=True, detach=True
                )
        except DockerException as e:
            raise RuntimeError(f"Failed to create container: {e}")

    async def start_container(self, detach: bool) -> None:
        try:
            container = self.client.containers.get(self.config.container_name)
            container.start()

            if not detach:
                await self._run_foreground_container(container)
        except DockerException as e:
            raise RuntimeError(f"Failed to start container: {e}")

    async def inject_workspace(self, files: Dict[str, bytes], dirs: Dict[str, Path]) -> None:
        try:
            container = self.client.containers.get(self.config.container_name)
            tar_bytes = self._build_workspace_tar(files, dirs)
            target = self.config.working_dir or "/workspace"
            container.put_archive(target, tar_bytes)
        except DockerException as e:
            raise RuntimeError(f"Failed to inject workspace: {e}")

    def _build_workspace_tar(self, files: Dict[str, bytes], dirs: Dict[str, Path]) -> bytes:
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tar:
            for arcname, data in files.items():
                info = tarfile.TarInfo(name=arcname)
                info.size = len(data)
                info.mode = 0o644
                tar.addfile(info, io.BytesIO(data))
            for arcname, src in dirs.items():
                tar.add(str(src), arcname=arcname, recursive=True, filter=self._tar_filter)
        return buf.getvalue()

    @staticmethod
    def _tar_filter(info: tarfile.TarInfo) -> Optional[tarfile.TarInfo]:
        basename = Path(info.name).name
        if basename == "__pycache__" or basename.endswith(".pyc"):
            return None
        return info

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
            self._stream_build_output(response)
        except DockerException as e:
            raise RuntimeError(f"Failed to build image: {e}")

    async def build_base_image(self, tag: str, dockerfile_bytes: bytes, runtime_requirements_bytes: bytes, package_source_root: Path) -> None:
        try:
            buf = io.BytesIO()
            with tarfile.open(fileobj=buf, mode="w") as tar:
                self._add_bytes_to_tar(tar, "Dockerfile", dockerfile_bytes)
                self._add_bytes_to_tar(tar, "runtime-requirements.txt", runtime_requirements_bytes)
                tar.add(
                    str(package_source_root),
                    arcname=f"src/{package_source_root.name}",
                    recursive=True,
                    filter=self._tar_filter,
                )
            buf.seek(0)

            response = self.client.api.build(
                fileobj=buf,
                custom_context=True,
                tag=tag,
                rm=True, forcerm=True, decode=True,
            )
            self._stream_build_output(response)
        except DockerException as e:
            raise RuntimeError(f"Failed to build base image: {e}")

    async def build_derived_image(self, base_image: str, requirements_path: Path, tag: str, labels: Optional[Dict[str, str]] = None) -> None:
        try:
            dockerfile = (
                f"FROM {base_image}\n"
                "COPY requirements.txt /tmp/requirements.txt\n"
                "RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt\n"
            ).encode("utf-8")
            requirements_bytes = requirements_path.read_bytes()

            buf = io.BytesIO()
            with tarfile.open(fileobj=buf, mode="w") as tar:
                self._add_bytes_to_tar(tar, "Dockerfile", dockerfile)
                self._add_bytes_to_tar(tar, "requirements.txt", requirements_bytes)
            buf.seek(0)

            response = self.client.api.build(
                fileobj=buf,
                custom_context=True,
                tag=tag,
                labels=labels or {},
                rm=True, forcerm=True, decode=True,
            )
            self._stream_build_output(response)
        except DockerException as e:
            raise RuntimeError(f"Failed to build derived image: {e}")

    def _stream_build_output(self, response) -> None:
        for chunk in response:
            if "stream" in chunk:
                sys.stdout.write(chunk["stream"])
                sys.stdout.flush()
            elif "errorDetail" in chunk:
                raise RuntimeError(chunk["errorDetail"]["message"])

    @staticmethod
    def _add_bytes_to_tar(tar: tarfile.TarFile, name: str, data: bytes) -> None:
        info = tarfile.TarInfo(name=name)
        info.size = len(data)
        info.mode = 0o644
        tar.addfile(info, io.BytesIO(data))

    async def pull_image(self) -> None:
        try:
            self.client.images.pull(self.config.image)
        except DockerException as e:
            raise RuntimeError(f"Failed to pull image: {e}")

    async def pull_image_by_tag(self, tag: str) -> None:
        try:
            self.client.images.pull(tag)
        except DockerException as e:
            raise RuntimeError(f"Failed to pull image: {e}")

    async def remove_image(self, force: bool = False) -> None:
        try:
            self.client.images.remove(image=self.config.image, force=force)
        except NotFound:
            pass
        except DockerException as e:
            raise RuntimeError(f"Failed to remove image: {e}")

    async def remove_image_by_tag(self, tag: str, force: bool = False) -> None:
        try:
            self.client.images.remove(image=tag, force=force)
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

    async def exists_image_by_tag(self, tag: str) -> bool:
        try:
            return True if self.client.images.get(tag) else False
        except NotFound:
            return False
        except DockerException as e:
            raise RuntimeError(f"Failed to check image: {e}")

    async def get_image_label(self, tag: str, label: str) -> Optional[str]:
        try:
            image = self.client.images.get(tag)
            return (image.labels or {}).get(label)
        except NotFound:
            return None
        except DockerException as e:
            raise RuntimeError(f"Failed to read image label: {e}")

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
