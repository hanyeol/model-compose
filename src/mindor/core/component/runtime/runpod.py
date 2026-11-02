from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union
from mindor.dsl.schema.component import ComponentConfig
from mindor.dsl.schema.runtime import RunPodRuntimeConfig
from mindor.core.component.base import ComponentGlobalConfigs
from mindor.core.component.runtime.common import (
    ComponentRuntimeManager,
    ComponentRuntimeProxy,
    ComponentRuntimeWorker,
)
from mindor.core.foundation.runtime.ipc_message import IpcMessage
from mindor.core.foundation.runtime.ipc_websocket_channel import IpcWebsocketTransport, IpcWebsocketChannel
from mindor.core.foundation.variable.time import parse_time
from mindor.core.runtime.runpod import RunPodRuntime
from mindor.core.utils.transport.runpod_client import RunPodError
from mindor.core.component.runtime.base.ipc_message import IpcStartPayload
from mindor.core.foundation.project import get_component_state_path
from mindor.core.foundation.package import mindor as mindor_package
from mindor.core.logger import logging
import argparse, asyncio, base64, json, os, secrets, sys

# Pod bootstrap pins — intentionally hardcoded (not DSL fields) to avoid
# surfacing an "escape hatch" users would feel obliged to customise.
_POD_BASE_IMAGE: str             = "pytorch/pytorch:2.13.0-cuda13.2-cudnn9-runtime"
_POD_WORKER_MODULE: str          = "mindor.core.component.runtime.runpod"

# Container-disk workspace used when the pod has no network volume
# mounted — ephemeral, so every launch pays extract + install.
_POD_DEFAULT_WORKSPACE_DIR: str  = "/root/.mindor"

# Short attach probe before paying the upload+install path. Long enough to
# cover one RunPod proxy round-trip plus a retry; short enough that a
# bootstrap-stage pod rolls over to the full bootstrap path quickly.
_ATTACH_PROBE_TIMEOUT: float     = 10.0

class ComponentRunPodRuntimeWorker(ComponentRuntimeWorker):
    """Component-side worker running inside a RunPod pod over a WebSocket."""
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

class ComponentRunPodRuntimeProxy(ComponentRuntimeProxy):
    """WebSocket-based IPC proxy for RunPod-spawned workers."""
    channel: IpcWebsocketTransport

    async def _send_message(self, message: bytes) -> None:
        await self.channel.send(message)

    async def _recv_message(self) -> Optional[bytes]:
        return await self.channel.recv()

class ComponentRunPodRuntimeManager(ComponentRuntimeManager):
    """Manager for a component backed by a RunPod GPU pod."""
    def __init__(
        self,
        component_id: str,
        component_config: ComponentConfig,
        global_configs: ComponentGlobalConfigs,
    ):
        super().__init__(component_id, component_config, global_configs)

        self._runtime_config: RunPodRuntimeConfig = component_config.runtime
        self._start_timeout = parse_time(self._runtime_config.start_timeout) if self._runtime_config.start_timeout is not None else None
        self._stop_timeout  = parse_time(self._runtime_config.stop_timeout) if self._runtime_config.stop_timeout is not None else None

        self._auth_token: Optional[str] = None
        self._runtime: Optional[RunPodRuntime] = None

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        return [ "runpod", "websockets", "aiohttp" ]

    async def _setup(self) -> None:
        self._runtime = RunPodRuntime(
            worker_id=self.worker_id,
            config=self._runtime_config,
        )

        # Claim an existing pod only when a prior session recorded both its
        # pod_id and auth_token — that pair is the host's proof of ownership
        # over the pod. Without it, a same-named pod on the account belongs
        # to someone else (e.g. a parallel compose project) and must not be
        # touched; fall through to a fresh create instead.
        state = self._load_pod_state()

        if state is not None:
            pod_id, self._auth_token = state

            if await self._runtime.claim(pod_id):
                logging.info(
                    "runpod: component '%s' claimed pod %s",
                    self.worker_id,
                    self._runtime.pod_id,
                )

                return

            logging.warning(
                "runpod: recorded pod %s for component '%s' is gone; creating a fresh one",
                pod_id,
                self.worker_id,
            )

        await self._provision_runtime()

    async def _teardown(self) -> None:
        if self._runtime is None:
            return

        try:
            await self._runtime.remove()
            self._discard_pod_state()
        finally:
            self._runtime = None

    async def _launch(self) -> IpcWebsocketTransport:
        try:
            await self._runtime.start()
        except RunPodError as e:
            # Resume can fail permanently when the pod's host machine ran out
            # of free GPUs while stopped (reallocated to another user), or on
            # any other RunPod-side terminal state. Terminate the zombie pod
            # and create a fresh one — our source/deps/model caches live on
            # the network volume, so the new pod reuses them via claim-less
            # bootstrap and warm restart.
            logging.warning(
                "runpod: component '%s' failed to resume pod %s: %s",
                self.worker_id,
                self._runtime.pod_id,
                e,
            )

            logging.warning(
                "runpod: terminating pod %s and provisioning a fresh one for component '%s'",
                self._runtime.pod_id,
                self.worker_id,
            )

            await self._runtime.remove()
            self._discard_pod_state()

            await self._provision_runtime()

        # Pod may already carry a live worker (claimed from a prior session
        # whose bootstrap finished and whose WS server is still listening on
        # worker_port). Probe cheaply before paying the full upload+install
        # path — on hit, the WS server owns the port, so an upload POST would
        # come back as HTTP 502 from the RunPod proxy anyway.
        try:
            transport = await self._attach_channel(timeout=_ATTACH_PROBE_TIMEOUT)

            logging.info(
                "runpod: component '%s' attached to pod %s without re-bootstrap (worker already serving)",
                self.worker_id,
                self._runtime.pod_id,
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
                    "runpod: component '%s' skipped install; pod %s already has the current `mindor` package",
                    self.worker_id,
                    self._runtime.pod_id,
                )
            else:
                logging.info(
                    "runpod: component '%s' installed `mindor` package on pod %s",
                    self.worker_id,
                    self._runtime.pod_id,
                )

            return await self._attach_channel()
        except BaseException:
            # The pod may be RUNNING and burning GPU time; best-effort stop
            # cuts billing while leaving the pod around for the next
            # start() to retry. Attach failures are often transient too
            # (slow bootstrap exceeding start_timeout), so don't terminate.
            try:
                await self._runtime.stop()
            except Exception:
                pass
            raise

    async def _shutdown(self, channel: IpcWebsocketTransport) -> None:
        try:
            await channel.close()
        except Exception as e:
            logging.warning("runpod: component '%s' channel close failed: %s", self.worker_id, e)

        await self._runtime.stop()

    def _create_proxy(self, channel: IpcWebsocketTransport) -> ComponentRunPodRuntimeProxy:
        proxy = ComponentRunPodRuntimeProxy(
            self.worker_id,
            self.component_config,
            self.global_configs,
            channel,
        )

        proxy._start_timeout = self._start_timeout
        proxy._stop_timeout  = self._stop_timeout

        return proxy

    async def _attach_channel(self, timeout: Optional[float] = None) -> IpcWebsocketTransport:
        """A pod reaches RUNNING well before its bootstrap command binds the
        websocket port, so the first few connects usually fail. Retry until
        ``timeout`` runs out (defaults to ``start_timeout``). Callers that
        want a cheap "is worker already up?" probe pass a small ``timeout``."""
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
                        f"pod {self._runtime.pod_id} worker did not accept websocket connection "
                        f"within {budget}s: {e}"
                    ) from e

                await asyncio.sleep(min(10.0, 2.0 * attempt))

        logging.info(
            "runpod: component '%s' websocket transport connected to pod %s",
            self.worker_id,
            self._runtime.pod_id,
        )

        return transport

    async def _provision_runtime(self) -> None:
        """Create a brand-new pod, mint a fresh auth token, and persist the
        pair so the next session can claim it. Used both on first-time setup
        and as the recovery path when a resume fails irrecoverably."""
        self._auth_token = secrets.token_urlsafe(32)

        await self._runtime.create(
            image=self._runtime_config.image or _POD_BASE_IMAGE,
            env=self._build_pod_environment(),
            docker_args=self._build_pod_bootstrap(self._runtime_config.worker_port),
        )

        # Keep the pod RUNNING: `_launch` runs immediately after and would
        # just pay a resume round-trip (~30s) to flip STOPPED back to RUNNING.
        # Billing exposure is bounded by `_shutdown`'s stop on normal exit.
        self._save_pod_state(self._runtime.pod_id, self._auth_token)

        logging.info(
            "runpod: component '%s' provisioned (pod %s)",
            self.worker_id,
            self._runtime.pod_id,
        )

    def _build_pod_bootstrap(self, worker_port: int) -> str:
        """Shell command run as the pod's docker CMD — writes the one-shot
        upload server to disk, runs it on the worker port to receive the
        host-shipped mindor package (or respond 304 when the cached version
        already matches), installs the bootstrap requirements, then execs
        the websocket worker on the same port. Re-extraction and
        re-install are skipped when the cached version matches, so warm
        restarts are near-instant.

        No embedded ``"``: RunPod's GraphQL layer wraps ``dockerArgs`` in
        double quotes without escaping, so any ``"`` here would terminate
        the GraphQL string.
        """
        # Encode the upload-server script in base64 so it travels through the
        # outer shell quoting and RunPod's GraphQL layer intact — the latter
        # wraps `dockerArgs` in double quotes without escaping, so any `"` or
        # `\n` embedded in the script would terminate the GraphQL string.
        upload_server_script = self._get_mindor_upload_server_script()
        upload_server_script = base64.b64encode(upload_server_script.encode("utf-8")).decode("ascii")

        workspace_root = self._get_pod_workspace_root()
        pip_cache_dir  = f"{workspace_root}/.pip-cache"
        mindor_src_dir = f"{workspace_root}/.mindor-src"
        site_pkgs_dir  = f"{workspace_root}/.site-packages"

        return (
            "bash -lc '"

            # Ensure ffmpeg is on PATH (model components routinely need it).
            "(command -v ffmpeg >/dev/null 2>&1) || "
            "(apt-get update && apt-get install -y --no-install-recommends ffmpeg) && "

            # Prepare pip cache, mindor package cache, and site-packages dir
            # under workspace_root. When a network volume is attached, these all
            # survive container recreations; without one they're ephemeral
            # and every launch pays extract + install.
            f"mkdir -p {pip_cache_dir} {mindor_src_dir} {site_pkgs_dir} && "
            f"export PIP_CACHE_DIR={pip_cache_dir} && "

            # Materialize the one-shot upload server (base64-encoded above)
            # and run it on the worker port. Exits 0 after extracting the
            # host-shipped source, 10 on a cache hit, non-zero on failure.
            f"echo {upload_server_script} | base64 -d > /tmp/upload_server.py && "
            f"python3 /tmp/upload_server.py --port {worker_port} --upload-path {mindor_src_dir}; "

            # Branch on the server's exit code: new source → reinstall pip
            # deps and only then stamp .version (so a mid-install crash does
            # not look like a cache hit on the next launch); cache hit →
            # skip reinstall; any other code → abort the whole bootstrap.
            f"server_rc=$?; "
            f"if [ $server_rc -eq 0 ]; then "
            f"pip install --upgrade --target={site_pkgs_dir} "
            f"websockets -r {mindor_src_dir}/mindor/core/runtime/bootstrap/requirements.txt && "
            f"echo $MINDOR_SRC_VERSION > {mindor_src_dir}/.version; "
            f"elif [ $server_rc -ne 10 ]; then exit $server_rc; "
            f"fi && "

            # Hand control to the websocket worker on the same port. Source
            # and deps are both reachable via PYTHONPATH off workspace_root —
            # survives container recreations when the volume is mounted,
            # hot-swaps on launch.
            f"export PYTHONPATH={mindor_src_dir}:{site_pkgs_dir}:$PYTHONPATH && "
            f"exec python -m {_POD_WORKER_MODULE} --port {worker_port}"
            "'"
        )

    def _build_pod_environment(self) -> Dict[str, str]:
        env: Dict[str, str] = {}

        # Point HF cache under the same workspace root as mindor source and
        # site-packages — persistent when a network volume is attached, so
        # re-pulls are free; ephemeral otherwise.
        env["HF_HOME"] = f"{self._get_pod_workspace_root()}/.cache/huggingface"

        # Rust-backed concurrent downloader — RunPod network bandwidth is high
        # enough that the throughput win is substantial, and large checkpoints
        # (tens of GB) make it worth paying the extra dependency by default.
        env["HF_HUB_ENABLE_HF_TRANSFER"] = "1"

        # Driver-triggered installs at runtime (e.g. torchaudio) target the
        # pod's system interpreter, which is PEP 668 externally-managed on
        # recent base images. Grant pip/uv permission to write to it.
        env["PIP_BREAK_SYSTEM_PACKAGES"] = "1"
        env["UV_BREAK_SYSTEM_PACKAGES"]  = "1"

        if self._runtime_config.network_volume_id:
            # MooseFS backs RunPod network volumes; its hardlink support is
            # unreliable across clients — uv's default hardlink install
            # produces stale file handles mid-write on larger wheels (seen
            # on CUDA shards).
            env["UV_LINK_MODE"] = "copy"

            # The container disk is ~50 GB. Xet reconstruction stages its
            # intermediates in TMPDIR and peaks at 1.5-2x the final weight
            # size, so a 180 GB model fills /tmp and fails with "Disk quota
            # exceeded". Point TMPDIR at the volume so staging has room.
            env["TMPDIR"] = f"{self._get_pod_workspace_root()}/tmp"

        if self._runtime_config.environment:
            env.update(self._runtime_config.environment)

        env["MINDOR_WORKER_AUTH_TOKEN"] = self._auth_token
        env["MINDOR_WORKER_PORT"] = str(self._runtime_config.worker_port)

        # Host-side mindor version — the pod's upload server replies 304 to
        # the host when its on-disk cache already matches this value, so the
        # host can skip extract + reinstall on warm restarts.
        env["MINDOR_SRC_VERSION"] = mindor_package.get_version()

        return env

    def _get_pod_workspace_root(self) -> str:
        """Mindor source + pip cache + site-packages root. Network volume
        mount when attached (persistent), container disk otherwise."""
        if self._runtime_config.network_volume_id:
            return self._runtime_config.volume_mount_path

        return _POD_DEFAULT_WORKSPACE_DIR

    def _load_pod_state(self):
        """Return ``(pod_id, auth_token)`` persisted from a prior session, or
        ``None`` when no prior state exists / the file is unreadable."""
        state_file = self._get_pod_state_path()

        if not state_file.exists():
            return None

        try:
            state = json.loads(state_file.read_text())
            return state["pod_id"], state["auth_token"]
        except (OSError, ValueError, KeyError):
            return None

    def _save_pod_state(self, pod_id: str, auth_token: str) -> None:
        """Persist ``(pod_id, auth_token)`` so the next session can claim
        this pod instead of paying the create cost again. 0600 file perms."""
        state_file = self._get_pod_state_path()
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps({"pod_id": pod_id, "auth_token": auth_token}))
        state_file.chmod(0o600)

    def _discard_pod_state(self) -> None:
        """Remove the persisted ``(pod_id, auth_token)`` after the pod is gone."""
        state_file = self._get_pod_state_path()
        state_file.unlink(missing_ok=True)

    def _get_pod_state_path(self):
        """Where this component's pod state (pod_id + auth_token) lives on
        the host, scoped by compose project namespace."""
        return get_component_state_path(self.worker_id) / "runpod.json"

def _worker_factory(message: IpcMessage, websocket: Any) -> ComponentRunPodRuntimeWorker:
    payload = IpcStartPayload.model_validate(message.payload or {})

    return ComponentRunPodRuntimeWorker(
        payload.component_id,
        payload.component_config,
        payload.global_configs,
        websocket,
    )

def main() -> None:
    """Entrypoint when launched as `python -m mindor.core.component.runtime.runpod`."""
    parser = argparse.ArgumentParser(prog="mindor-runpod-worker")
    parser.add_argument("--port", type=int, default=int(os.environ.get("MINDOR_WORKER_PORT", "8000")))
    parser.add_argument("--host", type=str, default="0.0.0.0")
    args = parser.parse_args()

    auth_token = os.environ.get("MINDOR_WORKER_AUTH_TOKEN")

    if not auth_token:
        # Without the shared secret the websocket endpoint is open to the
        # internet via the RunPod proxy URL. Refuse to serve.
        print("runpod: MINDOR_WORKER_AUTH_TOKEN env is required", file=sys.stderr)
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
