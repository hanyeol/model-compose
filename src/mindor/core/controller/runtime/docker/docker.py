from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from mindor.dsl.schema.controller import ControllerConfig, ControllerWebUIDriver
from mindor.dsl.schema.controller.adapter.impl.types import ControllerAdapterType
from mindor.dsl.schema.runtime import DockerRuntimeConfig, DockerBuildConfig, DockerPortConfig, DockerVolumeConfig, DockerHealthCheck
from mindor.core.runtime.docker import DockerRuntimeManager
from mindor.core.logger import logging
from mindor.version import __version__
from ..specs import ControllerRuntimeSpecs
from pathlib import Path
import re, yaml, hashlib

_REQUIREMENTS_HASH_LABEL = "mindor.requirements-sha256"

class DockerImageKind(str, Enum):
    BASE    = "base"
    DERIVED = "derived"
    USER    = "user"

class DockerRuntimeLauncher:
    def __init__(self, config: ControllerConfig, verbose: bool):
        self.config: ControllerConfig = config
        self.verbose: bool = verbose
        self._image_kind: DockerImageKind = DockerImageKind.BASE
        self._base_image_tag: Optional[str] = None
        self._derived_image_tag: Optional[str] = None
        self._requirements_path: Path = Path.cwd() / "requirements.txt"

        self._configure_runtime_config()

    def _configure_runtime_config(self) -> None:
        adapter_ports = self._resolve_adapter_ports()

        self._base_image_tag = f"mindor/controller:{__version__}"

        if self.config.runtime.image:
            self._image_kind = DockerImageKind.USER
        elif self.config.runtime.build:
            self._image_kind = DockerImageKind.USER
            self.config.runtime.image = f"mindor/controller-{self._project_name()}:latest"
        elif self._has_user_requirements():
            self._image_kind = DockerImageKind.DERIVED
            self._derived_image_tag = f"mindor/controller-{self._project_name()}:{__version__}"
            self.config.runtime.image = self._derived_image_tag
        else:
            self._image_kind = DockerImageKind.BASE
            self.config.runtime.image = self._base_image_tag

        if not self.config.runtime.container_name:
            self.config.runtime.container_name = self.config.name or f"mindor-controller-{self._project_name()}"

        if not self.config.runtime.working_dir:
            self.config.runtime.working_dir = "/workspace"

        if self.config.runtime.ports is None:
            webui_port = getattr(self.config.webui, "port", None)
            self.config.runtime.ports = list(set(adapter_ports + ([ webui_port ] if webui_port else [])))

        # Automatically add host.docker.internal for host machine access
        if not self.config.runtime.extra_hosts:
            self.config.runtime.extra_hosts = {}
        if "host.docker.internal" not in self.config.runtime.extra_hosts:
            self.config.runtime.extra_hosts["host.docker.internal"] = "host-gateway"

    def _resolve_adapter_ports(self) -> List[int]:
        ports = []
        for adapter in self.config.adapters:
            if adapter.type in [ ControllerAdapterType.QUEUE_SUBSCRIBER ]:
                continue
            if hasattr(adapter, 'port'):
                ports.append(adapter.port)
        return ports

    def _project_name(self) -> str:
        # Follows docker-compose: compose `name:` wins, else sanitized cwd basename.
        # Sanitization rule: lowercased, only [a-z0-9_-], must start with [a-z0-9].
        raw = self.config.name or Path.cwd().resolve().name
        sanitized = re.sub(r"[^a-z0-9_-]", "", raw.lower()).lstrip("_-")
        return sanitized or "default"

    def _has_user_requirements(self) -> bool:
        if not self._requirements_path.exists():
            return False
        for line in self._requirements_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                return True
        return False

    def _requirements_hash(self) -> str:
        return hashlib.sha256(self._requirements_path.read_bytes()).hexdigest()

    async def launch(self, specs: ControllerRuntimeSpecs, detach: bool) -> None:
        docker = DockerRuntimeManager(self.config.runtime, self.verbose)

        if self._image_kind != DockerImageKind.USER:
            await self._ensure_base_image(docker)

        if self._image_kind == DockerImageKind.DERIVED:
            await self._ensure_derived_image(docker)

        if await docker.is_container_running():
            logging.info("Stopping running Docker container before restarting...")
            await docker.stop_container()

        if await docker.exists_container():
            await docker.remove_container(force=True)

        logging.info("Creating Docker container...")
        await docker.create_container()

        await self._inject_workspace(docker, specs)

        logging.info("Starting Docker container (%s mode)...", "detached" if detach else "foreground")
        await docker.start_container(detach)

    async def terminate(self) -> None:
        docker = DockerRuntimeManager(self.config.runtime, self.verbose)

        if await docker.exists_container():
            await docker.remove_container(force=True)

        if self._image_kind == DockerImageKind.DERIVED and self._derived_image_tag:
            if await docker.exists_image_by_tag(self._derived_image_tag):
                await docker.remove_image_by_tag(self._derived_image_tag)

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def _ensure_base_image(self, docker: DockerRuntimeManager) -> None:
        if await docker.exists_image_by_tag(self._base_image_tag):
            return

        if self._version_tag() != "latest":
            logging.debug("Pulling base image %s...", self._base_image_tag)
            try:
                await docker.pull_image_by_tag(self._base_image_tag)
                if await docker.exists_image_by_tag(self._base_image_tag):
                    logging.info("Base image pulled successfully.")
                    return
            except Exception as e:
                logging.debug("Base image pull failed: %s — falling back to local build.", e)

        logging.info("Building base image %s locally...", self._base_image_tag)
        dockerfile_path = Path(__file__).resolve().parent / "context" / "Dockerfile"
        runtime_requirements_path = Path(mindor.__file__).resolve().parent / "core" / "runtime" / "base" / "requirements.txt"
        package_source_root = Path(mindor.__file__).resolve().parent

        await docker.build_base_image(
            tag=self._base_image_tag,
            dockerfile_bytes=dockerfile_path.read_bytes(),
            runtime_requirements_bytes=runtime_requirements_path.read_bytes(),
            package_source_root=package_source_root,
        )
        logging.info("Base image built successfully.")

    async def _ensure_derived_image(self, docker: DockerRuntimeManager) -> None:
        assert self._derived_image_tag is not None
        current_hash = self._requirements_hash()

        if await docker.exists_image_by_tag(self._derived_image_tag):
            stored_hash = await docker.get_image_label(self._derived_image_tag, _REQUIREMENTS_HASH_LABEL)
            if stored_hash == current_hash:
                return
            logging.info("requirements.txt changed — rebuilding derived image.")
            await docker.remove_image_by_tag(self._derived_image_tag, force=True)

        logging.info("Building derived image %s...", self._derived_image_tag)
        await docker.build_derived_image(
            base_image=self._base_image_tag,
            requirements_path=self._requirements_path,
            tag=self._derived_image_tag,
            labels={ _REQUIREMENTS_HASH_LABEL: current_hash },
        )
        logging.info("Derived image built successfully.")

    async def _inject_workspace(self, docker: DockerRuntimeManager, specs: ControllerRuntimeSpecs) -> None:
        compose_yaml = yaml.dump(specs.generate_native_runtime_specs(), sort_keys=False).encode("utf-8")
        files: Dict[str, bytes] = { "model-compose.yml": compose_yaml }
        dirs: Dict[str, Path] = {}

        server_dir = getattr(self.config.webui, "server_dir", None)
        if server_dir:
            resolved = (Path.cwd() / server_dir).resolve()
            if resolved.exists():
                dirs["webui/server"] = resolved

        static_dir = getattr(self.config.webui, "static_dir", None)
        if static_dir:
            resolved = (Path.cwd() / static_dir).resolve()
            if resolved.exists():
                dirs["webui/static"] = resolved

        await docker.inject_workspace(files, dirs)
