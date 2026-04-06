from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.controller import ControllerConfig
from mindor.dsl.schema.runtime import AppleContainerRuntimeConfig, AppleContainerBuildConfig, AppleContainerVolumeConfig
from mindor.core.runtime.apple_container import AppleContainerRuntimeManager
from mindor.core.logger import logging
from ..specs import ControllerRuntimeSpecs
from pathlib import Path
import mindor, shutil, yaml, os

class AppleContainerRuntimeLauncher:
    def __init__(self, config: ControllerConfig, verbose: bool):
        self.config: ControllerConfig = config
        self.verbose: bool = verbose

        self._configure_runtime_config()

    def _configure_runtime_config(self) -> None:
        adapter_ports = [ adapter.port for adapter in self.config.adapters if hasattr(adapter, 'port') ]
        first_port = adapter_ports[0] if adapter_ports else 8080

        if not self.config.runtime.image:
            if not self.config.runtime.build:
                self.config.runtime.build = AppleContainerBuildConfig(context=".container", dockerfile="Dockerfile")
            self.config.runtime.image = f"mindor/controller-{first_port}:latest"

        if not self.config.runtime.container_name:
            self.config.runtime.container_name = self.config.name or f"mindor-controller-{first_port}"

        if not self.config.runtime.ports:
            webui_port = getattr(self.config.webui, "port", None)
            self.config.runtime.ports = list(set(adapter_ports + ([webui_port] if webui_port else [])))

    async def launch(self, specs: ControllerRuntimeSpecs, detach: bool) -> None:
        manager = AppleContainerRuntimeManager(self.config.runtime, self.verbose)

        await self._prepare_build_context(specs)

        if not await manager.exists_image():
            logging.debug("Checking if container image can be pulled...")
            try:
                await manager.pull_image()
            except Exception as e:
                logging.debug("Container image pull failed: %s — will try building instead.", e)
            else:
                if not await manager.exists_image():
                    raise RuntimeError("Container image pull completed, but image is still missing.")
                logging.info("Container image pulled successfully.")

        if not await manager.exists_image():
            logging.debug("Building container image locally. This may take a few minutes...")
            try:
                await manager.build_image()
                logging.info("Container image build completed successfully.")
            except Exception as e:
                logging.error("Container image build failed: %s", e)
                raise

        # Create volumes and setup DNS (Apple Container specific)
        await manager.create_volumes()
        await manager.setup_dns()

        if await manager.is_container_running():
            logging.info("Stopping running container before restarting...")
            await manager.stop_container()

        logging.info("Starting container (%s mode)...", "detached" if detach else "foreground")
        await manager.start_container(detach)

    async def terminate(self) -> None:
        manager = AppleContainerRuntimeManager(self.config.runtime, self.verbose)

        if await manager.exists_container():
            await manager.remove_container(force=True)

        if await manager.exists_image():
            await manager.remove_image()

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def _prepare_build_context(self, specs: ControllerRuntimeSpecs) -> None:
        context_dir = Path.cwd() / ".container"
        if context_dir.exists():
            shutil.rmtree(context_dir)

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
