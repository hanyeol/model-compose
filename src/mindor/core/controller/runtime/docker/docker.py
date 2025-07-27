from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.controller import ControllerConfig
from mindor.dsl.schema.runtime import DockerRuntimeConfig, DockerBuildConfig, DockerPortConfig, DockerVolumeConfig, DockerHealthCheck
from mindor.core.runtime.docker import DockerRuntimeManager
from ..specs import ControllerRuntimeSpecs
from pathlib import Path
import mindor, shutil, yaml

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

    async def launch(self, specs: ControllerRuntimeSpecs, detach: bool):
        docker = DockerRuntimeManager(self.config.runtime, self.verbose)

        await self._prepare_docker_context(specs)

        if not await docker.exists_image():
            try:
                await docker.pull_image()
            except:
                pass

        if not await docker.exists_image():
            try:
                await docker.build_image()
            except Exception as e:
                pass

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

    async def _prepare_docker_context(self, specs: ControllerRuntimeSpecs) -> None:
        # Prepare context directory
        context_dir = Path.cwd() / ".docker"
        if context_dir.exists():
            shutil.rmtree(context_dir)

        # Copy context files
        context_files_root = Path(__file__).resolve().parent / "context"
        shutil.copytree(
            src=str(context_files_root), 
            dst=context_dir
        )

        # Copy source files
        source_files_root = Path(mindor.__file__).resolve().parent
        target_dir = context_dir / "src" / source_files_root.name
        shutil.copytree(
            src=str(source_files_root), 
            dst=target_dir, 
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
        )

        # Generate model-compose.yml
        with open(context_dir / "model-compose.yml", "w") as f:
            yaml.dump(specs.generate_native_runtime_specs(), f, sort_keys=False)

        # Copy or generate requirements.txt
        file_path = Path.cwd() / "requirements.txt"
        target_path = Path(context_dir) / file_path.name
        if file_path.exists():
            shutil.copy(file_path, target_path)
        else:
            target_path.touch()
