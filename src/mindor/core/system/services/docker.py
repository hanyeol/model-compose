from mindor.dsl.schema.system.impl.docker import DockerSystemConfig
from mindor.dsl.schema.system.impl.types import SystemType
from mindor.core.system.base import SystemService, register_system
from mindor.core.foundation.containers.docker import (
    DockerContainerRunner,
    DockerImageBuilder,
)
from mindor.core.logger import logging
import shutil


@register_system(SystemType.DOCKER)
class DockerSystem(SystemService):
    """Docker-compose-style system service: builds/pulls an image, creates
    a container from the user-supplied `DockerSystemConfig`, and manages
    its lifecycle.

    Delegates SDK calls to the foundation helpers `DockerImageBuilder` and
    `DockerContainerRunner` — this class itself only encodes the
    docker-compose-up flow (image first, then container)."""
    config: DockerSystemConfig

    def __init__(self, id: str, config: DockerSystemConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self._configure_system_config()

        self._builder: DockerImageBuilder = DockerImageBuilder(verbose=True)
        self._container: DockerContainerRunner = DockerContainerRunner(
            config=self.config,
            verbose=True,
        )

    def _configure_system_config(self) -> None:
        if not self.config.container_name:
            self.config.container_name = f"mindor-system-{self.id}"

    async def _setup(self) -> None:
        if not shutil.which("docker"):
            raise FileNotFoundError("'docker' command not found. Please install Docker to use docker systems.")

        if self.config.build:
            build = self.config.build
            await self._builder.build(
                tag=self.config.image,
                path=build.context,
                dockerfile=build.dockerfile,
                build_args=build.args,
                cache_from=build.cache_from,
                labels=build.labels,
                network_mode=build.network,
                pull=build.pull,
                target=build.target,
            )
        elif self.config.image:
            if not await self._builder.exists(self.config.image):
                await self._builder.pull(self.config.image)

    async def _serve(self) -> None:
        await self._container.create()
        await self._container.start(detach=True)
        logging.info(f"Docker container started: {self.config.container_name or self.config.image}")

    async def _shutdown(self) -> None:
        try:
            await self._container.stop()
            await self._container.remove()
            logging.info(f"Docker container stopped: {self.config.container_name or self.config.image}")
        except Exception as e:
            logging.warning(f"Docker container cleanup failed: {e}")

    async def _is_ready(self) -> bool:
        return await self._container.is_running()
