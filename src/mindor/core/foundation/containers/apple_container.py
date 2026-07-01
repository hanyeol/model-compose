from __future__ import annotations

from typing import Union, Optional, Dict, List
from dataclasses import dataclass
from mindor.dsl.schema.containers.apple_container import (
    AppleContainerConfig,
    AppleContainerBuildConfig,
    AppleContainerPortConfig,
    AppleContainerVolumeConfig,
)
from mindor.core.utils.containers.apple_container_client import AppleContainerClient
from mindor.core.logger import logging
import asyncio, json, signal

@dataclass
class AppleContainerMount:
    type: str
    source: str
    target: str
    read_only: bool = False

class AppleContainerPortsResolver:
    def __init__(self, ports: Optional[List[Union[str, int, AppleContainerPortConfig]]]):
        self.ports: Optional[List[Union[str, int, AppleContainerPortConfig]]] = ports

    def resolve(self) -> Dict[str, str]:
        """Normalize the user's `ports` config into a `{container: host}`
        mapping. Container ports include their `/protocol` suffix when
        specified (e.g. `"53/udp"`), matching docker SDK convention."""
        ports: Dict[str, str] = {}

        for port in self.ports or []:
            if isinstance(port, int):
                ports[str(port)] = str(port)
                continue

            if isinstance(port, str):
                spec, _, protocol = port.partition("/")
                published, _, target = spec.rpartition(":")
                container = f"{target}/{protocol}" if protocol else target
                ports[container] = published or target
                continue

            if isinstance(port, AppleContainerPortConfig):
                if port.published is None:
                    continue
                container = f"{port.target}/{port.protocol}" if port.protocol else str(port.target)
                ports[container] = str(port.published)
                continue

        return ports

class AppleContainerMountsResolver:
    def __init__(self, volumes: Optional[List[Union[str, AppleContainerVolumeConfig]]]):
        self.volumes: Optional[List[Union[str, AppleContainerVolumeConfig]]] = volumes

    def resolve(self) -> List[AppleContainerMount]:
        return [ self._get_volume_mount(volume) for volume in self.volumes or [] ]

    def _get_volume_mount(self, volume: Union[str, AppleContainerVolumeConfig]) -> AppleContainerMount:
        if isinstance(volume, str):
            parts = volume.split(":")
            source, target = parts[0], parts[1]
            read_only = len(parts) > 2 and parts[2] == "ro"
            mount_type = "bind" if source.startswith(("/", ".")) else "volume"

            return AppleContainerMount(
                type=mount_type,
                source=source,
                target=target,
                read_only=read_only
            )
        else:
            source = volume.source or volume.name or ""
            mount_type = volume.type

            if mount_type is None:
                mount_type = "bind" if source.startswith(("/", ".")) else "volume"

            return AppleContainerMount(
                type=mount_type,
                source=source,
                target=volume.target,
                read_only=bool(volume.read_only),
            )

@dataclass
class AppleContainerBuildParams:
    """Inputs for `AppleContainerImageBuilder.build`. Mirrors
    `AppleContainerBuildConfig`."""
    context: Optional[str] = None
    dockerfile: Optional[str] = None
    args: Optional[Dict[str, Union[str, int, float, bool]]] = None
    target: Optional[str] = None
    labels: Optional[Dict[str, str]] = None
    pull: Optional[bool] = None

    @classmethod
    def from_config(cls, config: AppleContainerBuildConfig) -> AppleContainerBuildParams:
        return cls(
            context=config.context,
            dockerfile=config.dockerfile,
            args=config.args,
            target=config.target,
            labels=config.labels,
            pull=config.pull,
        )

@dataclass
class AppleContainerParams:
    """Inputs for `AppleContainerRunner`. Mirrors `AppleContainerConfig`."""
    image: Optional[str] = None
    container_name: Optional[str] = None
    ports: Optional[List[Union[str, int, AppleContainerPortConfig]]] = None
    networks: Optional[List[str]] = None
    volumes: Optional[List[Union[str, AppleContainerVolumeConfig]]] = None
    environment: Optional[Dict[str, Union[str, int, float, bool]]] = None
    env_file: Optional[Union[str, List[str]]] = None
    command: Optional[Union[str, List[str]]] = None
    entrypoint: Optional[Union[str, List[str]]] = None
    working_dir: Optional[str] = None
    user: Optional[str] = None
    cpus: Optional[Union[str, float]] = None
    mem_limit: Optional[str] = None
    labels: Optional[Dict[str, str]] = None
    build: Optional[AppleContainerBuildConfig] = None

    @classmethod
    def from_config(cls, config: AppleContainerConfig) -> AppleContainerParams:
        return cls(
            image=config.image,
            container_name=config.container_name,
            ports=config.ports,
            networks=config.networks,
            volumes=config.volumes,
            environment=config.environment,
            env_file=config.env_file,
            command=config.command,
            entrypoint=config.entrypoint,
            working_dir=config.working_dir,
            user=config.user,
            cpus=config.cpus,
            mem_limit=config.mem_limit,
            labels=config.labels,
            build=config.build,
        )

class AppleContainerImageBuilder:
    """Builds, pulls, inspects, and removes Apple Container images via the
    `container` CLI. Stateless."""
    def __init__(self, verbose: bool = False):
        self.verbose: bool = verbose

        self._client = AppleContainerClient(verbose=verbose)

    async def build(
        self,
        tag: Optional[str],
        *,
        path: Optional[str] = None,
        dockerfile: Optional[str] = None,
        build_args: Optional[Dict[str, str]] = None,
        labels: Optional[Dict[str, str]] = None,
        target: Optional[str] = None,
        pull: Optional[bool] = None,
    ) -> None:
        """Build an image via the `container build` CLI.

        Mirrors the subset of `DockerImageBuilder.build` that the Apple
        Container CLI supports. The CLI does not accept stdin tar streams,
        so callers wanting in-memory context should materialize a directory
        via `archive_to_dir` and pass its path here.
        """
        args: List[str] = []

        if tag:
            args.extend([ "-t", tag ])

        if dockerfile:
            args.extend([ "-f", dockerfile ])

        if target:
            args.extend([ "--target", target ])

        if pull:
            args.append("--pull")

        for key, value in (build_args or {}).items():
            args.extend([ "--build-arg", f"{key}={value}" ])

        for key, value in (labels or {}).items():
            args.extend([ "-l", f"{key}={value}" ])

        args.append(path or ".")

        await self._client.run("build", args=args, capture_output=False)

    async def pull(self, tag: str) -> None:
        await self._client.run([ "image", "pull" ], args=[ tag ], capture_output=False)

    async def remove(self, tag: str, force: bool = False) -> None:
        # `force` is accepted for signature parity with `DockerImageBuilder.remove`;
        # the Apple Container CLI's `image rm` has no equivalent flag, so we ignore it.
        try:
            await self._client.run([ "image", "rm" ], args=[ tag ])
        except RuntimeError:
            pass

    async def exists(self, tag: str) -> bool:
        try:
            process = await self._client.run([ "image", "ls" ], raise_on_error=False)
            stdout, _ = await process.communicate()
            return tag in stdout.decode()
        except Exception:
            return False

    async def get_label(self, tag: str, label: str) -> Optional[str]:
        """Read a single label off an image via `container image inspect`.

        Mirrors `DockerImageBuilder.get_label` so launcher-side derived-image
        caching (sha256 of `requirements.txt`) works identically. Returns
        `None` when the image is missing or the label is absent. The Apple
        Container CLI emits OCI inspect JSON; we read the conventional
        `config.Labels` field and fall back to top-level `annotations` to
        tolerate minor schema drift across CLI versions.
        """
        try:
            process = await self._client.run(
                [ "image", "inspect" ], args=[ tag ], raise_on_error=False,
            )
            stdout, _ = await process.communicate()
            if process.returncode != 0:
                return None
            payload = json.loads(stdout.decode() or "null")
        except Exception:
            return None

        entries = payload if isinstance(payload, list) else [payload] if payload else []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            config = entry.get("config")
            if isinstance(config, dict):
                labels = config.get("Labels") or config.get("labels")
                if isinstance(labels, dict) and label in labels:
                    return labels[label]
            annotations = entry.get("annotations")
            if isinstance(annotations, dict) and label in annotations:
                return annotations[label]
        return None

class AppleContainerRunner:
    """Lifecycle wrapper around a single Apple Container.

    Pure lifecycle:
    - Runs the container from `AppleContainerParams` in detached
      or foreground mode.
    - On stop, asks the CLI for a graceful stop and tears the container
      down.

    Image build / pull / inspect lives in `AppleContainerImageBuilder`.
    """
    def __init__(self, params: AppleContainerParams, verbose: bool = False):
        self.params: AppleContainerParams = params
        self.verbose: bool = verbose

        self._client = AppleContainerClient(verbose=verbose)
        self._shutdown_event: asyncio.Event = asyncio.Event()

    async def create(self, tty: bool = True, stdin_open: bool = True) -> None:
        """Create a stopped container from `self.params`. Mirrors
        `DockerContainerRunner.create` so launcher-side lifecycle
        (`provision_runtime` → `create` → `start`) is identical across
        backends. The Apple Container CLI's `container create` accepts the
        same `-t`/`-i` flags as docker, so the kwargs map 1:1."""
        args = await self._compose_container_args(tty=tty, stdin_open=stdin_open)
        await self._client.run("create", args=args)

    async def start(self, detach: bool) -> None:
        """Start a previously `create()`d container. `detach=True` returns
        immediately; `detach=False` attaches stdout/stderr/stdin and waits
        for the container to exit."""
        args: List[str] = []
        if not detach:
            args.extend([ "-a", "-i" ])
        args.append(self.params.container_name)

        await self._client.run("start", args=args, capture_output=detach)

        if not detach:
            await self._run_foreground_container()

    async def _compose_container_args(self, tty: bool, stdin_open: bool) -> List[str]:
        """Build the argv shared by `container create` (and historically
        `container run`). Side effect: pre-creates any named volumes the
        mounts reference, since the Apple Container CLI does not auto-create
        them like the docker SDK does."""
        args: List[str] = []

        if self.params.container_name:
            args.extend([ "--name", self.params.container_name ])

        if tty:
            args.append("-t")
        if stdin_open:
            args.append("-i")

        for container, host in AppleContainerPortsResolver(self.params.ports).resolve().items():
            args.extend([ "-p", f"{host}:{container}" ])

        for mount in AppleContainerMountsResolver(self.params.volumes).resolve():
            if mount.type == "volume":
                try:
                    await self._client.run([ "volume", "create" ], args=[ mount.source ])
                except RuntimeError:
                    pass
            mount_spec = f"type={mount.type},source={mount.source},target={mount.target}"
            if mount.read_only:
                mount_spec += ",readonly"
            args.extend([ "--mount", mount_spec ])

        for network in self.params.networks or []:
            args.extend([ "--network", network ])

        for key, value in (self.params.environment or {}).items():
            args.extend([ "-e", f"{key}={value}" ])

        if self.params.env_file:
            env_files = [ self.params.env_file ] if isinstance(self.params.env_file, str) else self.params.env_file
            for env_file in env_files:
                args.extend([ "--env-file", env_file ])

        if self.params.entrypoint is not None:
            entrypoint = self.params.entrypoint
            if isinstance(entrypoint, list):
                entrypoint = " ".join(entrypoint)
            args.extend([ "--entrypoint", entrypoint ])

        if self.params.working_dir is not None:
            args.extend([ "-w", self.params.working_dir ])

        if self.params.user is not None:
            args.extend([ "-u", self.params.user ])

        if self.params.cpus is not None:
            args.extend([ "--cpus", str(self.params.cpus) ])

        if self.params.mem_limit is not None:
            args.extend([ "--memory", self.params.mem_limit ])

        for key, value in (self.params.labels or {}).items():
            args.extend([ "-l", f"{key}={value}" ])

        args.append(self.params.image)

        if self.params.command:
            if isinstance(self.params.command, str):
                args.append(self.params.command)
            else:
                args.extend(self.params.command)

        return args

    async def stop(self, timeout: Optional[float] = None) -> None:
        args: List[str] = []
        if timeout is not None:
            args.extend([ "-t", str(int(timeout)) ])
        args.append(self.params.container_name)
        try:
            await self._client.run("stop", args=args)
        except RuntimeError as e:
            logging.warning("Failed to stop container '%s': %s", self.params.container_name, e)

    async def remove(self, force: bool = False) -> None:
        args: List[str] = []

        if force:
            args.append("-f")

        args.append(self.params.container_name)
        try:
            await self._client.run("rm", args=args)
        except RuntimeError:
            pass

    async def is_running(self) -> bool:
        try:
            process = await self._client.run("ls", raise_on_error=False)
            stdout, _ = await process.communicate()
            return self.params.container_name in stdout.decode()
        except Exception:
            return False

    async def exists(self) -> bool:
        try:
            process = await self._client.run("ls", raise_on_error=False)
            stdout, _ = await process.communicate()
            return self.params.container_name in stdout.decode()
        except Exception:
            return False

    async def _run_foreground_container(self) -> None:
        self._register_shutdown_signals()
        await self._shutdown_event.wait()
        logging.info(
            "Stopping container '%s' gracefully...",
            self.params.container_name,
        )
        await self.stop()

    def _register_shutdown_signals(self) -> None:
        signal.signal(signal.SIGINT,  self._handle_shutdown_signal)
        signal.signal(signal.SIGTERM, self._handle_shutdown_signal)

    def _handle_shutdown_signal(self, signum, frame) -> None:
        self._shutdown_event.set()
