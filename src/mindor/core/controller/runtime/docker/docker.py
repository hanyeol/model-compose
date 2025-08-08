from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.controller import ControllerConfig, ControllerWebUIDriver
from mindor.dsl.schema.runtime import DockerRuntimeConfig, DockerBuildConfig, DockerPortConfig, DockerVolumeConfig, DockerHealthCheck
from mindor.core.runtime.docker import DockerRuntimeManager
from mindor.core.logger import logging
from ..specs import ControllerRuntimeSpecs
from pathlib import Path
import mindor, shutil, yaml, os

class DockerRuntimeLauncher:
    def __init__(self, config: ControllerConfig, verbose: bool):
        self.config: ControllerConfig = config
        self.verbose: bool = verbose

        self._configure_runtime_config()

    def _configure_runtime_config(self) -> None:
        if not self.config.runtime.image:
            if not self.config.runtime.build:
                self.config.runtime.build = DockerBuildConfig(context=".docker", dockerfile="Dockerfile")
            self.config.runtime.image = f"mindor/controller-{self.config.port}:latest"

        if not self.config.runtime.container_name:
            self.config.runtime.container_name = self.config.name or f"mindor-controller-{self.config.port}"

        if not self.config.runtime.ports:
            self.config.runtime.ports = [ port for port in [ self.config.port, getattr(self.config.webui, "port", None) ] if port ]

    async def launch(self, specs: ControllerRuntimeSpecs, detach: bool) -> None:
        docker = DockerRuntimeManager(self.config.runtime, self.verbose)

        await self._prepare_docker_context(specs)

        if not await docker.exists_image():
            logging.debug("Checking if Docker image can be pulled...")
            try:
                await docker.pull_image()
            except Exception as e:
                logging.debug("Docker image pull failed: %s — will try building instead.", e)
            else:
                if not await docker.exists_image():
                    raise RuntimeError("Docker image pull completed, but image is still missing.")
                logging.info("Docker image pulled successfully.")
 
        if not await docker.exists_image():
            logging.debug("Building Docker image locally. This may take a few minutes...")
            try:
                await docker.build_image()
                logging.info("Docker image build completed successfully.")
            except Exception as e:
                logging.error("Docker image build failed: %s", e)
                raise

        if await docker.is_container_running():
            logging.info("Stopping running Docker container before restarting...")
            await docker.stop_container()

        logging.info("Starting Docker container (%s mode)...", "detached" if detach else "foreground")
        await docker.start_container(detach)

    async def terminate(self) -> None:
        docker = DockerRuntimeManager(self.config.runtime, self.verbose)

        if await docker.exists_container():
            await docker.remove_container(force=True)

        if await docker.exists_image():
            await docker.remove_image()

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def _prepare_docker_context(self, specs: ControllerRuntimeSpecs) -> None:
        # Prepare context directory
        context_dir = Path.cwd() / ".docker"
        if context_dir.exists():
            shutil.rmtree(context_dir)

        # Copy context files
        context_files_root = Path(__file__).resolve().parent / "context"
        shutil.copytree(
            src=context_files_root, 
            dst=context_dir
        )

        # Copy source files
        source_files_root = Path(mindor.__file__).resolve().parent
        target_dir = context_dir / "src" / source_files_root.name
        shutil.copytree(
            src=source_files_root, 
            dst=target_dir, 
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
        )

        # Copy or generate requirements.txt
        file_path = Path.cwd() / "requirements.txt"
        target_path = Path(context_dir) / file_path.name
        if file_path.exists():
            shutil.copy(file_path, target_path)
        else:
            target_path.touch()

        # Copy or generate webui directory
        Path(context_dir / "webui").mkdir(parents=True, exist_ok=True)

        if getattr(self.config.webui, "server_dir", None):
            server_dir = Path.cwd() / self.config.webui.server_dir
            target_dir = context_dir / "webui" / "server"
            shutil.copytree(
                src=server_dir,
                dst=target_dir
            )

        if getattr(self.config.webui, "static_dir", None):
            static_dir = Path.cwd() / self.config.webui.static_dir
            target_dir = context_dir / "webui" / "static"
            shutil.copytree(
                src=static_dir,
                dst=target_dir
            )

        # Generate model-compose.yml
        with open(context_dir / "model-compose.yml", "w") as f:
            yaml.dump(specs.generate_native_runtime_specs(), f, sort_keys=False)
