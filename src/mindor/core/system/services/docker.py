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
        self._configure_system_config()

        self._runtime: DockerRuntimeManager = DockerRuntimeManager(
            config=self._build_runtime_config(self.config),
            verbose=True,
        )

    def _configure_system_config(self) -> None:
        if not self.config.container_name:
            self.config.container_name = f"mindor-system-{self.id}"

    def _build_runtime_config(self, config: DockerSystemConfig) -> DockerRuntimeConfig:
        shared_fields = set(DockerRuntimeConfig.model_fields) & set(DockerSystemConfig.model_fields)
        return DockerRuntimeConfig(**{
            **{ k: getattr(config, k) for k in shared_fields },
            "type": RuntimeType.DOCKER,
        })

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
