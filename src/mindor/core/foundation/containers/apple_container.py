from __future__ import annotations

from typing import Union, Optional, Dict, List
from dataclasses import dataclass
from mindor.dsl.schema.containers.apple_container import (
    AppleContainerConfig,
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

    def resolve(self) -> List[str]:
        """Normalize `ports` into fully-formed `-p` values for the `container` CLI:
        `[host_ip:]host_port:container_port[/protocol]`."""
        specs: List[str] = []

        for port in self.ports or []:
            if isinstance(port, int):
                specs.append(f"{port}:{port}")
                continue

            if isinstance(port, str):
                specs.append(port)
                continue

            if isinstance(port, AppleContainerPortConfig):
                if port.host_port is None:
                    continue
                container_part = f"{port.container_port}/{port.protocol}" if port.protocol else str(port.container_port)
                host_part = f"{port.host_ip}:{port.host_port}" if port.host_ip else str(port.host_port)
                specs.append(f"{host_part}:{container_part}")
                continue

        return specs

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
class AppleContainerOptions:
    """Backend-supplied values used by `AppleContainerRunner` when the user's
    `AppleContainerConfig` leaves the corresponding field unset. `options`
    wins over `config` — see `AppleContainerRunner` for the merge order."""
    image: Optional[str] = None
    container_name: Optional[str] = None
    entrypoint: Optional[Union[str, List[str]]] = None
    ports: Optional[List[Union[str, int, AppleContainerPortConfig]]] = None

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

        Mirrors `DockerImageBuilder.get_label` so manager-side derived-image
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
    - Runs the container from an `AppleContainerConfig` (plus optional
      backend-supplied `AppleContainerOptions`) in detached or foreground
      mode.
    - On stop, asks the CLI for a graceful stop and tears the container
      down.

    Image build / pull / inspect lives in `AppleContainerImageBuilder`.
    """
    def __init__(
        self,
        config: AppleContainerConfig,
        options: Optional[AppleContainerOptions] = None,
        verbose: bool = False,
    ):
        self.config: AppleContainerConfig = config
        self.options: AppleContainerOptions = options or AppleContainerOptions()
        self.verbose: bool = verbose

        self._client = AppleContainerClient(verbose=verbose)
        self._shutdown_event: asyncio.Event = asyncio.Event()

    @property
    def container_name(self) -> Optional[str]:
        return self.options.container_name or self.config.container_name

    @property
    def image(self) -> Optional[str]:
        return self.options.image or self.config.image

    async def create(self, tty: bool = True, stdin_open: bool = True) -> None:
        """Create a stopped container from the config/options pair. Mirrors
        `DockerContainerRunner.create` so manager-side lifecycle
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
        args.append(self.container_name)

        await self._client.run("start", args=args, capture_output=detach)

        if not detach:
            await self._run_foreground_container()

    async def _compose_container_args(self, tty: bool, stdin_open: bool) -> List[str]:
        """Build the argv shared by `container create` (and historically
        `container run`). Side effect: pre-creates any named volumes the
        mounts reference, since the Apple Container CLI does not auto-create
        them like the docker SDK does."""
        args: List[str] = []

        if self.container_name:
            args.extend([ "--name", self.container_name ])

        if tty:
            args.append("-t")
        if stdin_open:
            args.append("-i")

        for spec in AppleContainerPortsResolver(self.options.ports or self.config.ports).resolve():
            args.extend([ "-p", spec ])

        for mount in AppleContainerMountsResolver(self.config.volumes).resolve():
            if mount.type == "volume":
                try:
                    await self._client.run([ "volume", "create" ], args=[ mount.source ])
                except RuntimeError:
                    pass
            mount_spec = f"type={mount.type},source={mount.source},target={mount.target}"
            if mount.read_only:
                mount_spec += ",readonly"
            args.extend([ "--mount", mount_spec ])

        for network in self.config.networks or []:
            args.extend([ "--network", network ])

        for key, value in (self.config.environment or {}).items():
            args.extend([ "-e", f"{key}={value}" ])

        if self.config.env_file:
            env_files = [ self.config.env_file ] if isinstance(self.config.env_file, str) else self.config.env_file
            for env_file in env_files:
                args.extend([ "--env-file", env_file ])

        entrypoint = self.options.entrypoint or self.config.entrypoint
        if entrypoint is not None:
            if isinstance(entrypoint, list):
                entrypoint = " ".join(entrypoint)
            args.extend([ "--entrypoint", entrypoint ])

        if self.config.working_dir is not None:
            args.extend([ "-w", self.config.working_dir ])

        if self.config.user is not None:
            args.extend([ "-u", self.config.user ])

        if self.config.cpus is not None:
            args.extend([ "--cpus", str(self.config.cpus) ])

        if self.config.mem_limit is not None:
            args.extend([ "--memory", self.config.mem_limit ])

        for key, value in (self.config.labels or {}).items():
            args.extend([ "-l", f"{key}={value}" ])

        args.append(self.image)

        if self.config.command:
            if isinstance(self.config.command, str):
                args.append(self.config.command)
            else:
                args.extend(self.config.command)

        return args

    async def stop(self, timeout: Optional[float] = None) -> None:
        args: List[str] = []
        if timeout is not None:
            args.extend([ "-t", str(int(timeout)) ])
        args.append(self.container_name)
        try:
            await self._client.run("stop", args=args)
        except RuntimeError as e:
            logging.warning("Failed to stop container '%s': %s", self.container_name, e)

    async def remove(self, force: bool = False) -> None:
        args: List[str] = []

        if force:
            args.append("-f")

        args.append(self.container_name)
        try:
            await self._client.run("rm", args=args)
        except RuntimeError:
            pass

    async def is_running(self) -> bool:
        try:
            process = await self._client.run("ls", raise_on_error=False)
            stdout, _ = await process.communicate()
            return self.container_name in stdout.decode()
        except Exception:
            return False

    async def exists(self) -> bool:
        try:
            process = await self._client.run("ls", raise_on_error=False)
            stdout, _ = await process.communicate()
            return self.container_name in stdout.decode()
        except Exception:
            return False

    async def _run_foreground_container(self) -> None:
        self._register_shutdown_signals()
        await self._shutdown_event.wait()
        logging.info(
            "Stopping container '%s' gracefully...",
            self.container_name,
        )
        await self.stop()

    def _register_shutdown_signals(self) -> None:
        signal.signal(signal.SIGINT,  self._handle_shutdown_signal)
        signal.signal(signal.SIGTERM, self._handle_shutdown_signal)

    def _handle_shutdown_signal(self, signum, frame) -> None:
        self._shutdown_event.set()
