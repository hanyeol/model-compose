from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.runtime import DockerRuntimeConfig, DockerBuildConfig, DockerPortConfig, DockerVolumeConfig, DockerHealthCheck
from docker.types import Mount
from docker.errors import DockerException, NotFound
import asyncio, docker, sys

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

    async def start_container(self, detach: bool) -> None:
        try:
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
                detach=detach,
                labels=self.config.labels,
                network=self.config.networks[0] if self.config.networks else None,
                privileged=self.config.privileged,
                security_opt=self.config.security_opt,
                tty=not detach,
                stdin_open=not detach,
                restart_policy={ "Name": self.config.restart }
            )
            container.start()

            if not detach:
                for line in container.logs(stream=True, follow=True):
                    sys.stdout.buffer.write(line)
                    sys.stdout.flush()
                exit_status = container.wait()
                if exit_status.get("StatusCode", 0) != 0:
                    raise RuntimeError(f"Container exited with status {exit_status}")
            else:
                pass

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
            image = self.client.images.create(
                path=self.config.build.context,
                dockerfile=self.config.build.dockerfile,
                tag=self.config.image,
                buildargs=self.config.build.args or {},
                target=self.config.build.target,
                cache_from=self.config.build.cache_from or [],
                labels=self.config.build.labels or {},
                network_mode=self.config.build.network,
                pull=self.config.build.pull,
            )
            image.start()

            for line in image.logs(stream=True, follow=True):
                sys.stdout.buffer.write(line)
                sys.stdout.flush()
            exit_status = image.wait()
            if exit_status.get("StatusCode", 0) != 0:
                raise RuntimeError(f"Container exited with status {exit_status}")
        except DockerException as e:
            raise RuntimeError(f"Failed to build image: {e}")

    async def pull_image(self) -> None:
        try:
            self.client.images.pull(self.config.image)
        except DockerException as e:
            raise RuntimeError(f"Failed to pull image: {e}")

    async def remove_image(self) -> None:
        try:
            self.client.images.remove(image=self.config.image, force=True)
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
