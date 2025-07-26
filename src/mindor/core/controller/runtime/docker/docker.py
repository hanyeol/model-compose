from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.controller import ControllerConfig
from mindor.dsl.schema.runtime import DockerRuntimeConfig, DockerBuildConfig, DockerPortConfig, DockerVolumeConfig, DockerHealthCheck
from mindor.core.runtime.docker import DockerRuntimeManager
from pathlib import Path
import mindor, shutil

class DockerRuntimeLauncher:
    def __init__(self, config: ControllerConfig, verbose: bool):
        self.config: ControllerConfig = config
        self.verbose: bool = verbose

        self._configure_runtime_config()

    def _configure_runtime_config(self):
        if not self.config.runtime.image:
            if not self.config.runtime.build:
                self.config.runtime.build = DockerBuildConfig(context=".docker", dockerfile="Dockerfile")
            self.config.runtime.image = f"mindor/controller-{self.config.port}:latest"

        if not self.config.runtime.container_name:
            self.config.runtime.container_name = self.config.name or f"mindor-controller-{self.config.port}"

        if not self.config.runtime.ports:
            self.config.runtime.ports = [ port for port in [ self.config.port, getattr(self.config.webui, "port", None) ] if port ]

    async def launch(self, detach: bool):
        docker = DockerRuntimeManager(self.config.runtime, self.verbose)

        await self._prepare_docker_context()

        if not await docker.exists_image():
            try:
                await docker.pull_image()
            except:
                pass

        if not await docker.exists_image():
            try:
                await docker.build_image()
            except Exception as e:
                print(e)

        if await docker.exists_container():
            await docker.remove_container(force=True)

        await docker.start_container(detach)

    async def terminate(self):
        docker = DockerRuntimeManager(self.config.runtime, self.verbose)

        if await docker.exists_container():
            await docker.remove_container(force=True)

        if await docker.exists_image():
            await docker.remove_image()

        shutil.rmtree(".docker")

    async def _prepare_docker_context(self) -> None:
        # Copy source tree
        source_root = Path(mindor.__file__).resolve().parent
        target_dir = Path.cwd() / ".docker" / "src"

        def _ignore_filter(directory: str, contents: list[str]) -> list[str]:
            return [ name for name in contents if name in [ "__pycache__" ] ]

        if target_dir.exists():
            shutil.rmtree(target_dir)
        shutil.copytree(src=str(source_root), dst=target_dir / source_root.name, ignore=_ignore_filter)

        # Generate model-compose.yml
        # Generate .env file
