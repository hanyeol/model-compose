from __future__ import annotations

from typing import Any, Dict, List, Union
from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from mindor.dsl.schema.runtime import AppleContainerRuntimeConfig, DockerRuntimeConfig
from mindor.core.utils.archive import archive_to_dir, skip_python_artifacts
from mindor.core.logger import logging
import mindor, hashlib

ContainerRuntimeConfig = Union[DockerRuntimeConfig, AppleContainerRuntimeConfig]

_REQUIREMENTS_SHA256_LABEL = "mindor.requirements-sha256"

class ContainerImageKind(str, Enum):
    """How a manager should source its container image."""
    STANDARD = "standard"  # mindor's standard image (mindor/<role>:VERSION).
    DERIVED  = "derived"   # Standard image + user `requirements.txt` layer.
    CUSTOM   = "custom"    # Caller supplied an explicit image or build context.

class ContainerRuntimeBackend(ABC):
    """Shared image lifecycle for container-backed runtime managers."""
    def __init__(self, runtime_config: ContainerRuntimeConfig, verbose: bool = False):
        self.runtime_config: ContainerRuntimeConfig = runtime_config
        self.verbose: bool = verbose

        self._builder = self._create_builder()
        self._requirements_path: Path = Path.cwd() / "requirements.txt"
        self._setup_script_path: Path = Path.cwd() / "setup.sh"
        self._build_root: Path = Path.cwd() / ".build"
        self._image_kind: ContainerImageKind = self._resolve_image_kind()

    @property
    def image_kind(self) -> ContainerImageKind:
        return self._image_kind

    async def provision_runtime(self) -> Any:
        """Ensure the image exists, then recreate the container fresh."""
        runtime = self.resolve_runtime()

        if await runtime.is_running():
            await runtime.stop()

        if await runtime.exists():
            await runtime.remove(force=True)

        await self._ensure_runtime_image()
        await runtime.create(**self._container_create_options())

        return runtime

    async def teardown_runtime(self) -> None:
        """Tear down the container and drop any DERIVED image this manager produced."""
        runtime = self.resolve_runtime()

        if await runtime.exists():
            await runtime.remove(force=True)

        if self._image_kind == ContainerImageKind.DERIVED:
            derived_tag = self._derived_image_tag()
            if await self._builder.exists(derived_tag):
                await self._builder.remove(derived_tag)

    def resolve_runtime(self) -> Any:
        """Build a backend runtime from the injected runtime config. User-supplied
        `image` / `container_name` win; otherwise the backend's default is used."""
        options = self._resolve_container_options()

        if options.image is None:
            options.image = self._default_image_tag()

        if options.container_name is None:
            options.container_name = self._default_container_name()

        return self._create_runtime(options)

    def _container_create_options(self) -> Dict[str, Any]:
        """Extra kwargs forwarded to the backend's `runtime.create()`."""
        return {}

    async def _ensure_runtime_image(self) -> None:
        """Ensure the image this run will launch from exists, building/pulling as required by the image kind."""
        if self._image_kind == ContainerImageKind.CUSTOM:
            # User-supplied `image:` wins; otherwise fall back to our locally-built CUSTOM tag.
            await self._ensure_custom_image(self.runtime_config.image or self._custom_image_tag())
            return

        await self._ensure_standard_image(self._standard_image_tag())

        if self._image_kind == ContainerImageKind.DERIVED:
            await self._ensure_derived_image(self._derived_image_tag())

    async def _ensure_standard_image(self, image_tag: str) -> None:
        if await self._builder.exists(image_tag):
            logging.debug("Standard image %s already exists — skipping.", image_tag)
            return

        if self._version_tag(image_tag) != "latest":
            logging.debug("Pulling standard image %s...", image_tag)
            try:
                await self._builder.pull(image_tag)
                if await self._builder.exists(image_tag):
                    logging.info("Standard image %s pulled successfully.", image_tag)
                    return
            except Exception as e:
                logging.debug("Standard image pull failed: %s — falling back to local build.", e)

        logging.info("Building standard image %s locally...", image_tag)
        package_source_root = Path(mindor.__file__).resolve().parent
        assets_dir = self._image_assets_dir()
        dockerfile_path = assets_dir / "Dockerfile.standard"
        requirements_path = package_source_root / "core" / "runtime" / "bootstrap" / "requirements.txt"

        command_json = "[" + ", ".join(f'"{part}"' for part in self._standard_image_command()) + "]"
        dockerfile_bytes = dockerfile_path.read_bytes() + f"CMD {command_json}\n".encode("utf-8")

        files: Dict[str, Any] = {
            "Dockerfile": dockerfile_bytes,
            "standard-requirements.txt": requirements_path,
        }
        bootstrap_path = assets_dir / "bootstrap.sh"
        if bootstrap_path.is_file():
            files["bootstrap.sh"] = bootstrap_path

        with archive_to_dir(
            files=files,
            dirs={f"src/{package_source_root.name}": package_source_root},
            filter=skip_python_artifacts,
            root=self._build_root,
        ) as context_dir:
            await self._builder.build(
                tag=image_tag,
                path=str(context_dir),
            )
        logging.info("Standard image %s built successfully.", image_tag)

    async def _ensure_derived_image(self, image_tag: str) -> None:
        current_hash = self._derived_context_hash()

        if await self._builder.exists(image_tag):
            stored_hash = await self._builder.get_label(image_tag, _REQUIREMENTS_SHA256_LABEL)
            if stored_hash == current_hash:
                logging.debug("Derived image %s already up to date — skipping.", image_tag)
                return
            logging.info("Derived image context changed — rebuilding %s.", image_tag)
            await self._builder.remove(image_tag, force=True)

        logging.info("Building derived image %s...", image_tag)
        assets_dir = self._image_assets_dir()
        dockerfile_path = assets_dir / "Dockerfile.derived"

        # Both requirements.txt and setup.sh are optional at the project level;
        # the derived Dockerfile always COPYs them, so we fall back to shipped
        # no-op stubs when the user provided none.
        requirements_path = self._requirements_path if self._requirements_path.is_file() else assets_dir / "requirements.stub.txt"
        setup_script_path = self._setup_script_path if self._setup_script_path.is_file() else assets_dir / "setup.stub.sh"

        with archive_to_dir(
            files={
                "Dockerfile": dockerfile_path,
                "user-requirements.txt": requirements_path,
                "user-setup.sh": setup_script_path,
            },
            root=self._build_root,
        ) as context_dir:
            await self._builder.build(
                tag=image_tag,
                path=str(context_dir),
                build_args={"BASE_IMAGE": self._standard_image_tag()},
                labels={_REQUIREMENTS_SHA256_LABEL: current_hash},
            )
        logging.info("Derived image %s built successfully.", image_tag)

    async def _ensure_custom_image(self, image_tag: str) -> None:
        """Build from `build:` context, or pull `image:` if not already present locally."""
        build = self.runtime_config.build

        if build:
            logging.info("Building custom image %s...", image_tag)
            await self._builder.build(tag=image_tag, **self._resolve_build_params(build))
            logging.info("Custom image %s built successfully.", image_tag)
            return

        if await self._builder.exists(image_tag):
            logging.debug("Custom image %s already exists — skipping pull.", image_tag)
            return

        logging.info("Pulling custom image %s...", image_tag)
        await self._builder.pull(image_tag)
        logging.info("Custom image %s pulled successfully.", image_tag)

    def _resolve_image_kind(self) -> ContainerImageKind:
        """Classify the runtime as STANDARD / DERIVED / CUSTOM based on the
        user's runtime config and the workspace."""
        if self.runtime_config.image or self.runtime_config.build:
            return ContainerImageKind.CUSTOM

        if self._has_derived_context():
            return ContainerImageKind.DERIVED

        return ContainerImageKind.STANDARD

    def _has_derived_context(self) -> bool:
        if self._setup_script_path.is_file() or self._is_meaningful_requirements(self._requirements_path):
            return True
        return False

    @staticmethod
    def _is_meaningful_requirements(path: Path) -> bool:
        if path.is_file():
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    return True
        return False

    @abstractmethod
    def _image_assets_dir(self) -> Path:
        """Directory holding role-specific container build assets."""

    @abstractmethod
    def _default_image_tag(self) -> str:
        """Default image tag when the user did not supply `runtime.image`.
        (STANDARD/DERIVED default images; CUSTOM path with `build:` computes its own tag.)"""

    @abstractmethod
    def _default_container_name(self) -> str:
        """Default container name when the user did not supply `runtime.container_name`."""

    @abstractmethod
    def _standard_image_tag(self) -> str:
        """Tag for this manager's standard image."""

    @abstractmethod
    def _standard_image_command(self) -> List[str]:
        """CMD baked into this manager's standard image."""

    @abstractmethod
    def _derived_image_tag(self) -> str:
        """Tag for this manager's derived image (standard + user `requirements.txt` layer)."""

    @abstractmethod
    def _custom_image_tag(self) -> str:
        """Fallback tag for a locally-built CUSTOM image when the user only supplied `build:`."""

    @abstractmethod
    def _create_runtime(self, options: Any) -> Any:
        """Instantiate the backend-specific runtime from resolved `*ContainerOptions`."""

    @abstractmethod
    def _create_builder(self) -> Any:
        """Construct the backend-specific image builder."""

    @abstractmethod
    def _resolve_container_options(self) -> Any:
        """Translate the injected runtime config into a backend-specific `*ContainerOptions` dataclass."""

    @abstractmethod
    def _resolve_build_params(self, config: Any) -> Dict[str, Any]:
        """Translate the user's `build:` config into `**kwargs` for the backend builder's `build()`."""

    def _derived_context_hash(self) -> str:
        """Hash of the derived image's build context so we rebuild when either
        the pip requirements or the system setup script changes. Both files
        are optional; a missing one simply contributes no bytes."""
        h = hashlib.sha256()
        if self._requirements_path.is_file():
            h.update(b"\x00requirements.txt\x00")
            h.update(self._requirements_path.read_bytes())
        if self._setup_script_path.is_file():
            h.update(b"\x00setup.sh\x00")
            h.update(self._setup_script_path.read_bytes())
        return h.hexdigest()

    @staticmethod
    def _version_tag(tag: str) -> str:
        """Extract the version portion of `repo:tag`, defaulting to `'latest'`."""
        return tag.rsplit(":", 1)[-1] if ":" in tag else "latest"
