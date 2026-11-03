from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union
from mindor.dsl.schema.component import ComponentConfig
from mindor.dsl.schema.runtime import VastaiRuntimeConfig
from mindor.core.component.base import ComponentGlobalConfigs
from mindor.core.component.runtime.common import (
    ComponentRuntimeManager,
    ComponentRuntimeProxy,
    ComponentRuntimeWorker,
)
from mindor.core.foundation.runtime.ipc_message import IpcMessage
from mindor.core.foundation.runtime.ipc_websocket_channel import IpcWebsocketTransport, IpcWebsocketChannel
from mindor.core.foundation.variable.time import parse_time
from mindor.core.runtime.vastai import VastaiRuntime
from mindor.core.utils.transport.vastai_client import VastaiError
from mindor.core.component.runtime.base.ipc_message import IpcStartPayload
from mindor.core.foundation.project import get_component_state_path
from mindor.core.foundation.package import mindor as mindor_package
from mindor.core.logger import logging
import argparse, asyncio, json, os, secrets, sys

# Instance bootstrap pins — intentionally hardcoded (not DSL fields) to avoid
# surfacing an "escape hatch" users would feel obliged to customise.
_INSTANCE_BASE_IMAGE: str            = "pytorch/pytorch:2.13.0-cuda13.2-cudnn9-runtime"
_INSTANCE_WORKER_MODULE: str         = "mindor.core.component.runtime.vastai"

# Container-disk workspace used when the instance has no network volume
# linked — ephemeral, so every launch pays extract + install.
_INSTANCE_DEFAULT_WORKSPACE_DIR: str = "/root/.mindor"

# Short attach probe before paying the upload+install path. Long enough to
# cover one round-trip to the Vast host plus a retry; short enough that a
# bootstrap-stage instance rolls over to the full bootstrap path quickly.
_ATTACH_PROBE_TIMEOUT: float         = 10.0

class ComponentVastaiRuntimeWorker(ComponentRuntimeWorker):
    """Component-side worker running inside a Vast.ai instance over a WebSocket."""
    def __init__(
        self,
        component_id: str,
        component_config: ComponentConfig,
        global_configs: ComponentGlobalConfigs,
        websocket: Any,
    ):
        super().__init__(component_id, component_config, global_configs)

        self._websocket: Any = websocket

    async def _send_message(self, message: bytes) -> None:
        await self._websocket.send(message)

    async def _recv_message(self) -> Optional[bytes]:
        import websockets.exceptions

        try:
            frame = await self._websocket.recv()
        except websockets.exceptions.ConnectionClosed:
            return None

        if isinstance(frame, str):
            # Server contract is binary-only; a text frame is a protocol
            # violation. Treat as EOF so the dispatch loop winds down cleanly.
            return None

        return frame

    def _close_transport(self) -> None:
        if self._loop is None or self._websocket is None:
            return

        try:
            self._loop.create_task(self._websocket.close())
        except Exception:
            pass

class ComponentVastaiRuntimeProxy(ComponentRuntimeProxy):
    """WebSocket-based IPC proxy for Vast.ai-spawned workers."""
    channel: IpcWebsocketTransport

    async def _send_message(self, message: bytes) -> None:
        await self.channel.send(message)

    async def _recv_message(self) -> Optional[bytes]:
        return await self.channel.recv()

class ComponentVastaiRuntimeManager(ComponentRuntimeManager):
    """Manager for a component backed by a Vast.ai GPU instance."""
    def __init__(
        self,
        component_id: str,
        component_config: ComponentConfig,
        global_configs: ComponentGlobalConfigs,
    ):
        super().__init__(component_id, component_config, global_configs)

        self._runtime_config: VastaiRuntimeConfig = component_config.runtime
        self._start_timeout = parse_time(self._runtime_config.start_timeout) if self._runtime_config.start_timeout is not None else None
        self._stop_timeout  = parse_time(self._runtime_config.stop_timeout) if self._runtime_config.stop_timeout is not None else None

        self._auth_token: Optional[str] = None
        self._runtime: Optional[VastaiRuntime] = None

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        return [ "vastai", "websockets", "aiohttp" ]

    async def _setup(self) -> None:
        self._runtime = VastaiRuntime(
            worker_id=self.worker_id,
            config=self._runtime_config,
        )

        # Claim an existing instance only when a prior session recorded both
        # its instance_id and auth_token — that pair is the host's proof of
        # ownership over the instance. Without it, a same-labeled instance
        # on the account belongs to someone else (e.g. a parallel compose
        # project) and must not be touched; fall through to a fresh create
        # instead.
        state = self._load_instance_state()

        if state is not None:
            instance_id, self._auth_token = state

            if await self._runtime.claim(instance_id):
                logging.info(
                    "vastai: component '%s' claimed instance %s",
                    self.worker_id,
                    self._runtime.instance_id,
                )

                return

            logging.warning(
                "vastai: recorded instance %s for component '%s' is gone; creating a fresh one",
                instance_id,
                self.worker_id,
            )

        await self._provision_runtime()

    async def _teardown(self) -> None:
        if self._runtime is None:
            return

        try:
            await self._runtime.remove()
            self._discard_instance_state()
        finally:
            self._runtime = None

    async def _launch(self) -> IpcWebsocketTransport:
        try:
            await self._runtime.start()
        except VastaiError as e:
            # Resume can fail permanently when the instance's host machine
            # ran out of free GPUs while stopped (reallocated to another
            # user), or on any other Vast-side terminal state. Destroy the
            # zombie instance and create a fresh one — our source/deps/model
            # caches live on the network volume, so the new instance reuses
            # them via claim-less bootstrap and warm restart.
            logging.warning(
                "vastai: component '%s' failed to resume instance %s: %s",
                self.worker_id,
                self._runtime.instance_id,
                e,
            )

            logging.warning(
                "vastai: destroying instance %s and provisioning a fresh one for component '%s'",
                self._runtime.instance_id,
                self.worker_id,
            )

            await self._runtime.remove()
            self._discard_instance_state()

            await self._provision_runtime()

        # Instance may already carry a live worker (claimed from a prior
        # session whose bootstrap finished and whose WS server is still
        # listening on worker_port). Probe cheaply before paying the full
        # upload+install path — on hit, the WS server owns the port, so an
        # upload POST would come back as a connection refused anyway.
        try:
            transport = await self._attach_channel(timeout=_ATTACH_PROBE_TIMEOUT)

            logging.info(
                "vastai: component '%s' attached to instance %s without re-bootstrap (worker already serving)",
                self.worker_id,
                self._runtime.instance_id,
            )

            return transport
        except TimeoutError:
            pass

        try:
            status = await self._upload_mindor_source(
                url=f"{self._runtime.proxy_http_url}/",
                auth_token=self._auth_token,
                timeout=self._start_timeout,
            )

            if status == 304:
                logging.info(
                    "vastai: component '%s' skipped install; instance %s already has the current `mindor` package",
                    self.worker_id,
                    self._runtime.instance_id,
                )
            else:
                logging.info(
                    "vastai: component '%s' installed `mindor` package on instance %s",
                    self.worker_id,
                    self._runtime.instance_id,
                )

            return await self._attach_channel()
        except BaseException:
            # The instance may be running and burning GPU time; best-effort
            # stop cuts billing while leaving the instance around for the
            # next start() to retry. Attach failures are often transient too
            # (slow bootstrap exceeding start_timeout), so don't destroy.
            try:
                await self._runtime.stop()
            except Exception:
                pass
            raise

    async def _shutdown(self, channel: IpcWebsocketTransport) -> None:
        try:
            await channel.close()
        except Exception as e:
            logging.warning("vastai: component '%s' channel close failed: %s", self.worker_id, e)

        await self._runtime.stop()

    def _create_proxy(self, channel: IpcWebsocketTransport) -> ComponentVastaiRuntimeProxy:
        proxy = ComponentVastaiRuntimeProxy(
            self.worker_id,
            self.component_config,
            self.global_configs,
            channel,
        )

        proxy._start_timeout = self._start_timeout
        proxy._stop_timeout  = self._stop_timeout

        return proxy

    async def _attach_channel(self, timeout: Optional[float] = None) -> IpcWebsocketTransport:
        """A Vast.ai instance reaches running well before its onstart command
        binds the websocket port, so the first few connects usually fail.
        Retry until ``timeout`` runs out (defaults to ``start_timeout``).
        Callers that want a cheap "is worker already up?" probe pass a small
        ``timeout``."""
        budget = timeout if timeout is not None else self._start_timeout
        transport = IpcWebsocketTransport(
            url=self._runtime.proxy_websocket_url,
            auth_token=self._auth_token,
            connect_timeout=min(60.0, budget),
        )

        loop = asyncio.get_event_loop()
        deadline = loop.time() + budget
        attempt = 0

        while True:
            attempt += 1

            try:
                await transport.connect()
                break
            except Exception as e:
                if loop.time() > deadline:
                    raise TimeoutError(
                        f"instance {self._runtime.instance_id} worker did not accept websocket connection "
                        f"within {budget}s: {e}"
                    ) from e

                await asyncio.sleep(min(10.0, 2.0 * attempt))

        logging.info(
            "vastai: component '%s' websocket transport connected to instance %s",
            self.worker_id,
            self._runtime.instance_id,
        )

        return transport

    async def _provision_runtime(self) -> None:
        """Create a brand-new instance, mint a fresh auth token, and persist
        the pair so the next session can claim it. Used both on first-time
        setup and as the recovery path when a resume fails irrecoverably."""
        self._auth_token = secrets.token_urlsafe(32)

        await self._runtime.create(
            image=self._runtime_config.image or _INSTANCE_BASE_IMAGE,
            env=self._build_instance_environment(),
            onstart_cmd=self._build_instance_bootstrap(self._runtime_config.worker_port),
        )

        # Keep the instance running: `_launch` runs immediately after and
        # would just pay a resume round-trip to flip stopped back to running.
        # Billing exposure is bounded by `_shutdown`'s stop on normal exit.
        self._save_instance_state(self._runtime.instance_id, self._auth_token)

        logging.info(
            "vastai: component '%s' provisioned (instance %s)",
            self.worker_id,
            self._runtime.instance_id,
        )

    def _build_instance_bootstrap(self, worker_port: int) -> str:
        """Bash script Vast writes to ``/root/onstart.sh`` and bashes after
        container start — writes the one-shot upload server to disk, runs it
        on the worker port to receive the host-shipped mindor package (or
        respond 304 when the cached version already matches), installs the
        bootstrap requirements, then execs the websocket worker on the same
        port. Re-extraction and re-install are skipped when the cached
        version matches, so warm restarts are near-instant.

        Returned as a raw multi-line script body — no ``bash -lc '...'``
        wrapper. Vast's ``ssh`` runtype hands this file to bash itself; a
        self-wrapping ``bash -lc`` would double-shell the command and (worse)
        collide with Vast's own argv handling.
        """
        # Encode the upload-server script in base64 so it travels through the
        # on-disk script intact — any `"` or `\n` embedded verbatim in the
        # script would collide with the outer bash parser's own tokenization.
        upload_server_script = self._get_mindor_upload_server_script(encode_base64=True)

        workspace_root = self._get_instance_workspace_root()
        pip_cache_dir  = f"{workspace_root}/.pip-cache"
        mindor_src_dir = f"{workspace_root}/.mindor-src"
        site_pkgs_dir  = f"{workspace_root}/.site-packages"

        return (
            "#!/bin/bash\n"
            "set -e\n"

            # Ensure ffmpeg is on PATH (model components routinely need it).
            "(command -v ffmpeg >/dev/null 2>&1) || "
            "(apt-get update && apt-get install -y --no-install-recommends ffmpeg)\n"

            # Prepare pip cache, mindor package cache, and site-packages dir
            # under workspace_root. When a network volume is linked, these all
            # survive container recreations; without one they're ephemeral
            # and every launch pays extract + install.
            f"mkdir -p {pip_cache_dir} {mindor_src_dir} {site_pkgs_dir}\n"
            f"export PIP_CACHE_DIR={pip_cache_dir}\n"

            # Materialize the one-shot upload server (base64-encoded above)
            # and run it on the worker port. Exits 0 after extracting the
            # host-shipped source, 10 on a cache hit, non-zero on failure.
            f"echo {upload_server_script} | base64 -d > /tmp/upload_server.py\n"
            "set +e\n"
            f"python3 /tmp/upload_server.py --port {worker_port} --upload-path {mindor_src_dir}\n"
            "server_rc=$?\n"
            "set -e\n"

            # Branch on the server's exit code: new source → reinstall pip
            # deps and only then stamp .version (so a mid-install crash does
            # not look like a cache hit on the next launch); cache hit →
            # skip reinstall; any other code → abort the whole bootstrap.
            "if [ $server_rc -eq 0 ]; then\n"
            f"  pip install --upgrade --target={site_pkgs_dir} "
            f"websockets -r {mindor_src_dir}/mindor/core/runtime/bootstrap/requirements.txt\n"
            f"  echo $MINDOR_SRC_VERSION > {mindor_src_dir}/.version\n"
            "elif [ $server_rc -ne 10 ]; then\n"
            "  exit $server_rc\n"
            "fi\n"

            # Hand control to the websocket worker on the same port. Source
            # and deps are both reachable via PYTHONPATH off workspace_root —
            # survives container recreations when the volume is linked,
            # hot-swaps on launch.
            f"export PYTHONPATH={mindor_src_dir}:{site_pkgs_dir}:$PYTHONPATH\n"
            f"exec python -m {_INSTANCE_WORKER_MODULE} --port {worker_port}\n"
        )

    def _build_instance_environment(self) -> Dict[str, str]:
        env: Dict[str, str] = {}

        # Point HF cache under the same workspace root as mindor source and
        # site-packages — persistent when a network volume is linked, so
        # re-pulls are free; ephemeral otherwise.
        env["HF_HOME"] = f"{self._get_instance_workspace_root()}/.cache/huggingface"

        # Xet high-performance transfer path — Vast.ai network bandwidth is
        # high enough that the throughput win is substantial, and large
        # checkpoints (tens of GB) make this the default worth paying for.
        # Replaces the older HF_HUB_ENABLE_HF_TRANSFER, which huggingface_hub
        # deprecated once hf_transfer stopped being used.
        env["HF_XET_HIGH_PERFORMANCE"] = "1"

        # Driver-triggered installs at runtime (e.g. torchaudio) target the
        # instance's system interpreter, which is PEP 668 externally-managed
        # on recent base images. Grant pip/uv permission to write to it.
        env["PIP_BREAK_SYSTEM_PACKAGES"] = "1"
        env["UV_BREAK_SYSTEM_PACKAGES"]  = "1"

        if self._runtime_config.network_volume_id:
            # Vast network volumes are backed by remote block storage whose
            # hardlink support varies by host — uv's default hardlink install
            # can produce stale file handles mid-write on larger wheels.
            env["UV_LINK_MODE"] = "copy"

            # Xet reconstruction stages its intermediates in TMPDIR and peaks
            # at 1.5-2x the final weight size, so a 180 GB model fills the
            # container disk and fails with "Disk quota exceeded". Point
            # TMPDIR at the volume so staging has room.
            env["TMPDIR"] = f"{self._get_instance_workspace_root()}/tmp"

        if self._runtime_config.environment:
            env.update(self._runtime_config.environment)

        env["MINDOR_WORKER_AUTH_TOKEN"] = self._auth_token
        env["MINDOR_WORKER_PORT"] = str(self._runtime_config.worker_port)

        # Host-side mindor version — the instance's upload server replies 304
        # to the host when its on-disk cache already matches this value, so
        # the host can skip extract + reinstall on warm restarts.
        env["MINDOR_SRC_VERSION"] = mindor_package.get_version()

        return env

    def _get_instance_workspace_root(self) -> str:
        """Mindor source + pip cache + site-packages root. Network volume
        mount when linked (persistent), container disk otherwise."""
        if self._runtime_config.network_volume_id:
            return self._runtime_config.volume_mount_path

        return _INSTANCE_DEFAULT_WORKSPACE_DIR

    def _load_instance_state(self):
        """Return ``(instance_id, auth_token)`` persisted from a prior
        session, or ``None`` when no prior state exists / the file is
        unreadable."""
        state_file = self._get_instance_state_path()

        if not state_file.exists():
            return None

        try:
            state = json.loads(state_file.read_text())
            return state["instance_id"], state["auth_token"]
        except (OSError, ValueError, KeyError):
            return None

    def _save_instance_state(self, instance_id: str, auth_token: str) -> None:
        """Persist ``(instance_id, auth_token)`` so the next session can
        claim this instance instead of paying the create cost again. 0600
        file perms."""
        state_file = self._get_instance_state_path()
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps({"instance_id": instance_id, "auth_token": auth_token}))
        state_file.chmod(0o600)

    def _discard_instance_state(self) -> None:
        """Remove the persisted ``(instance_id, auth_token)`` after the
        instance is gone."""
        state_file = self._get_instance_state_path()
        state_file.unlink(missing_ok=True)

    def _get_instance_state_path(self):
        """Where this component's instance state (instance_id + auth_token)
        lives on the host, scoped by compose project namespace."""
        return get_component_state_path(self.worker_id) / "vastai.json"

def _worker_factory(message: IpcMessage, websocket: Any) -> ComponentVastaiRuntimeWorker:
    payload = IpcStartPayload.model_validate(message.payload or {})

    return ComponentVastaiRuntimeWorker(
        payload.component_id,
        payload.component_config,
        payload.global_configs,
        websocket,
    )

def main() -> None:
    """Entrypoint when launched as `python -m mindor.core.component.runtime.vastai`."""
    parser = argparse.ArgumentParser(prog="mindor-vastai-worker")
    parser.add_argument("--port", type=int, default=int(os.environ.get("MINDOR_WORKER_PORT", "8000")))
    parser.add_argument("--host", type=str, default="0.0.0.0")
    args = parser.parse_args()

    auth_token = os.environ.get("MINDOR_WORKER_AUTH_TOKEN")

    if not auth_token:
        # Without the shared secret the websocket endpoint is open to the
        # internet via the Vast host port mapping. Refuse to serve.
        print("vastai: MINDOR_WORKER_AUTH_TOKEN env is required", file=sys.stderr)
        sys.exit(2)

    channel = IpcWebsocketChannel(
        _worker_factory,
        auth_token=auth_token,
        host=args.host,
        port=args.port,
    )

    asyncio.run(channel.serve())

if __name__ == "__main__":
    main()
