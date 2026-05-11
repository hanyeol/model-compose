from mindor.dsl.schema.system.impl.docker import DockerSystemConfig
from mindor.dsl.schema.system.impl.types import SystemType
from mindor.dsl.schema.runtime.impl.docker import DockerRuntimeConfig
from mindor.dsl.schema.runtime.impl.types import RuntimeType
from mindor.core.system.base import SystemService, register_system
from mindor.core.runtime.docker.docker import DockerRuntimeManager
from mindor.core.logger import logging
import shutil

@register_system(SystemType.DOCKER)
class DockerSystem(SystemService):
    def __init__(self, id: str, config: DockerSystemConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.config: DockerSystemConfig = config
        self._runtime: DockerRuntimeManager = DockerRuntimeManager(
            config=self._build_runtime_config(),
            verbose=True,
        )

    async def _setup(self) -> None:
        if not shutil.which("docker"):
            raise RuntimeError("'docker' command not found. Please install Docker to use docker systems.")

        if self.config.build:
            await self._runtime.build_image()
        elif self.config.image:
            if not await self._runtime.exists_image():
                await self._runtime.pull_image()

    async def _serve(self) -> None:
        await self._runtime.start_container(detach=True)
        logging.info(f"Docker container started: {self.config.container_name or self.config.image}")

    async def _shutdown(self) -> None:
        try:
            await self._runtime.stop_container()
            await self._runtime.remove_container()
            logging.info(f"Docker container stopped: {self.config.container_name or self.config.image}")
        except Exception as e:
            logging.warning(f"Docker container cleanup failed: {e}")

    async def _is_ready(self) -> bool:
        return await self._runtime.is_container_running()

    def _build_runtime_config(self) -> DockerRuntimeConfig:
        return DockerRuntimeConfig(
            type=RuntimeType.DOCKER,
            image=self.config.image,
            build=self.config.build,
            container_name=self.config.container_name or f"mc-system-{self.id}",
            hostname=self.config.hostname,
            ports=self.config.ports,
            networks=self.config.networks,
            extra_hosts=self.config.extra_hosts,
            volumes=self.config.volumes,
            gpus=self.config.gpus,
            environment=self.config.environment,
            env_file=self.config.env_file,
            command=self.config.command,
            entrypoint=self.config.entrypoint,
            working_dir=self.config.working_dir,
            user=self.config.user,
            mem_limit=self.config.mem_limit,
            memswap_limit=self.config.memswap_limit,
            cpus=self.config.cpus,
            cpu_shares=self.config.cpu_shares,
            restart=self.config.restart,
            healthcheck=self.config.healthcheck,
            labels=self.config.labels,
            privileged=self.config.privileged,
            security_opt=self.config.security_opt,
        )
