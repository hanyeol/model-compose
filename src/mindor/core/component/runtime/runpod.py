from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, Optional
from mindor.dsl.schema.component import ComponentConfig
from mindor.dsl.schema.runtime import RunPodRuntimeConfig
from mindor.core.component.base import ComponentGlobalConfigs
from mindor.core.component.runtime.common import (
    ComponentRuntimeManager,
    ComponentRuntimeProxy,
    ComponentRuntimeWorker,
)
from mindor.core.foundation.runtime.ipc_message import IpcMessage
from mindor.core.foundation.runtime.ipc_ws_channel import IpcWsClientTransport, IpcWsServerChannel
from mindor.core.foundation.variable.time import parse_time
from mindor.core.runtime.runpod import RunPodHandle, RunPodLaunchError, RunPodRuntime
from mindor.core.component.runtime.base.ipc_message import IpcStartPayload
from mindor.core.logger import logging
import argparse, asyncio, os, secrets, sys

# Pod bootstrap pins — hardcoded on purpose. Keeping these out of the DSL
# avoids surfacing an "escape hatch" field users would then feel obliged to
# customise; bumps happen here in the module.
_POD_BASE_IMAGE: str     = "pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime"
_POD_GIT_REMOTE: str     = "https://github.com/hanyeol/model-compose.git"
_POD_GIT_REVISION: str   = "main"
_POD_WORKER_MODULE: str  = "mindor.core.component.runtime.runpod"
_POD_PIP_CACHE_DIR: str  = "/workspace/.pip-cache"

class ComponentRunPodRuntimeWorker(ComponentRuntimeWorker):
    """Component-side worker that runs inside the RunPod pod.

    Bridges IPC over a single long-lived WebSocket connection accepted by
    `IpcWsServerChannel`. Each WS binary frame carries exactly one serialized
    `IpcMessage`, so the transport maps 1:1 onto the base worker's
    `_send_message` / `_recv_message` contract.
    """
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
        # Close is async on `websockets`; schedule the close coroutine on the
        # worker's loop. We've already left the dispatch loop by this point,
        # so there is no risk of racing a concurrent recv/send.
        if self._loop is None or self._websocket is None:
            return

        try:
            self._loop.create_task(self._websocket.close())
        except Exception:
            pass

class ComponentRunPodRuntimeProxy(ComponentRuntimeProxy):
    """Parent-side IPC proxy that drives the pod worker over a WebSocket.

    The `channel` carried on the base class is an `IpcWsClientTransport`;
    each `_send_message` / `_recv_message` is a single WS binary frame
    carrying one serialized `IpcMessage`.
    """
    channel: IpcWsClientTransport

    async def _send_message(self, message: bytes) -> None:
        await self.channel.send(message)

    async def _recv_message(self) -> Optional[bytes]:
        return await self.channel.recv()

class ComponentRunPodRuntimeManager(ComponentRuntimeManager):
    """Manager for a component backed by a RunPod GPU pod.

    Differs from the container managers in three ways:

    1. **Lazy start.** `start()` does not provision a pod; the first `run()`
       call does. This lets `model-compose up` return immediately and keeps
       the pod stopped (and billing paused) between runs.
    2. **Idle stop.** After a run completes, a timer tracks inactivity and
       stops the pod once ``idle_timeout`` elapses. The next run transparently
       resumes it.
    3. **Pod reuse via `resume_pod`.** Once provisioned, the pod_id is cached
       so subsequent starts are resume (seconds) rather than fresh create
       (minutes), and the network volume keeps the model weights warm.
    """
    def __init__(
        self,
        component_id: str,
        component_config: ComponentConfig,
        global_configs: ComponentGlobalConfigs,
    ):
        super().__init__(component_id, component_config, global_configs)

        runtime_config: RunPodRuntimeConfig = component_config.runtime
        self._runtime_config: RunPodRuntimeConfig = runtime_config

        self._runpod: RunPodRuntime = RunPodRuntime(runtime_config)
        self._auth_token: str = secrets.token_urlsafe(32)

        self._pod_handle: Optional[RunPodHandle] = None
        self._launch_lock: asyncio.Lock = asyncio.Lock()
        self._active_requests: int = 0
        self._idle_timer_task: Optional[asyncio.Task] = None

        self._stop_timeout: Optional[float] = parse_time(runtime_config.stop_timeout) if runtime_config.stop_timeout else None
        self._idle_timeout: float = parse_time(runtime_config.idle_timeout)

    # ------------------------------------------------------------------
    # Lifecycle overrides (bypass ComponentRuntimeManager._launch/_shutdown)
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Register the component without provisioning a pod.

        First reclaims any pods left behind by a previous process (crash,
        clean exit without ``terminate_on_down``, or restart). We cannot
        safely adopt them: the WS auth token is a fresh per-session secret,
        so a resume would fail the handshake and we would terminate anyway.
        Terminate up-front for a predictable clean slate — the network
        volume keeps the model weights so the next `run()`'s fresh pod
        reloads instantly rather than redownloading.
        """
        await self._reclaim_orphan_pods()

        logging.info(
            "runpod: component '%s' registered; pod will start on first request",
            self.worker_id,
        )

    async def stop(self) -> None:
        """Tear down the proxy and either stop or terminate the pod."""
        self._cancel_idle_timer()

        if self._proxy is not None:
            try:
                await self._proxy.stop()
            except Exception as e:
                logging.warning("runpod: proxy stop failed: %s", e)
            self._proxy = None
            self._channel = None

        if self._pod_handle is not None:
            await self._shutdown_pod()

    async def run(
        self,
        action_id: str,
        run_id: str,
        input_data: Dict[str, Any],
        on_event: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
    ) -> Any:
        await self._ensure_pod_running()

        self._active_requests += 1
        self._cancel_idle_timer()
        try:
            return await self._proxy.run(action_id, run_id, input_data, on_event=on_event)
        finally:
            self._active_requests -= 1
            if self._active_requests == 0:
                self._schedule_idle_timer()

    # ------------------------------------------------------------------
    # Pod properties
    # ------------------------------------------------------------------

    @property
    def _pod_name(self) -> str:
        """RunPod `name` field used both to label newly created pods and to
        reclaim orphans left behind by a crashed/restarted parent."""
        return f"mindor-{self.worker_id}"

    # ------------------------------------------------------------------
    # Pod provisioning
    # ------------------------------------------------------------------

    async def _ensure_pod_running(self) -> None:
        """Guarantee a RUNNING pod + a live WS proxy before returning.

        If the pod is created / resumed but the WS attach then fails (bootstrap
        crashed, auth mismatch, Cloudflare proxy misroute), the pod would keep
        burning GPU time until the parent process notices. Terminate on that
        path so the caller sees a clean error with no runaway cost.
        """
        if self._proxy is not None and self._pod_handle is not None:
            return

        async with self._launch_lock:
            if self._proxy is not None and self._pod_handle is not None:
                return

            if self._pod_handle is None:
                await self._launch_pod()
            else:
                await self._resume_pod()

            try:
                await self._attach_proxy()
            except BaseException:
                await self._abort_pod_on_attach_failure()
                raise

    async def _abort_pod_on_attach_failure(self) -> None:
        """Terminate the pod when WS attach fails after it reached RUNNING.

        `terminate` (not `stop`) because the bootstrap command likely crashed
        or hung — a stop/resume would hit the same broken container. The
        network volume survives either way, so model weights are preserved.
        """
        pod_id = self._pod_handle.pod_id

        logging.warning("runpod: WS attach failed for pod %s; terminating to stop billing", pod_id)

        try:
            await self._runpod.terminate_pod(pod_id)
        finally:
            # Clear the handle unconditionally — a terminate_pod failure
            # (API down, quota, already deleted) must not cause the next
            # `_ensure_pod_running` call to try to resume a dead pod_id.
            self._pod_handle = None

    async def _launch_pod(self) -> None:
        config = self._runtime_config
        image = config.image or _POD_BASE_IMAGE

        env = {
            "WORKER_AUTH_TOKEN": self._auth_token,
            "WORKER_PORT": str(config.worker_port),
            # Point HF cache at the network volume so re-pulls are free.
            "HF_HOME": f"{config.volume_mount_path}/.cache/huggingface",
        }

        if config.environment:
            env.update({k: str(v) for k, v in config.environment.items()})

        docker_args = self._build_pod_bootstrap(config.worker_port)

        try:
            handle = await self._runpod.create_pod(
                name=self._pod_name,
                image=image,
                env=env,
                docker_args=docker_args,
            )
        except RunPodLaunchError:
            raise

        logging.info("runpod: pod %s is RUNNING (cost=%s/hr)", handle.pod_id, handle.cost_per_hr)

        self._pod_handle = handle

    async def _resume_pod(self) -> None:
        handle = await self._runpod.resume_pod(self._pod_handle.pod_id)

        logging.info("runpod: pod %s resumed", handle.pod_id)

        self._pod_handle = handle

    async def _attach_proxy(self) -> None:
        """Open a WS connection to the pod worker, then start the IPC proxy.

        A pod reaches RUNNING well before its bootstrap command (git-install
        + ``python -m mindor.core.component.runtime.runpod``) has bound the WS port, so the
        first few connects usually fail. Retry with a short backoff until
        ``start_timeout`` runs out.
        """
        transport = IpcWsClientTransport(
            url=self._pod_handle.proxy_ws_url,
            auth_token=self._auth_token,
            connect_timeout=min(60.0, parse_time(self._runtime_config.start_timeout)),
        )

        deadline = asyncio.get_event_loop().time() + parse_time(self._runtime_config.start_timeout)
        attempt = 0

        while True:
            attempt += 1
            try:
                await transport.connect()
                break
            except Exception as e:
                if asyncio.get_event_loop().time() > deadline:
                    raise RunPodLaunchError(
                        f"pod {self._pod_handle.pod_id} worker did not accept WS connection "
                        f"within start_timeout ({self._runtime_config.start_timeout}): {e}"
                    ) from e

                # Exponential-ish backoff capped at 10s; the first attempt
                # usually fails immediately (connection refused) so a 2s floor
                # keeps the loop from hammering the proxy.
                await asyncio.sleep(min(10.0, 2.0 * attempt))

        proxy = ComponentRunPodRuntimeProxy(
            self.worker_id,
            self.component_config,
            self.global_configs,
            transport,
        )
        proxy._stop_timeout = self._stop_timeout

        try:
            await proxy.start()
        except Exception:
            await transport.close()
            raise

        self._channel = transport
        self._proxy = proxy
        logging.info("runpod: WS proxy attached to pod %s", self._pod_handle.pod_id)

    async def _stop_pod(
        self,
        pod_id: str,
        max_attempts: int = 3,
        initial_delay: float = 2.0,
    ) -> None:
        """`stop_pod` with bounded exponential backoff.

        Billing keeps running until the pod is actually stopped, so a
        transient SDK/API hiccup on the first attempt must not leave the pod
        running forever. Raises the final failure so the caller can decide
        whether to log and move on, surface it to the operator, or escalate.
        """
        delay = initial_delay

        for attempt in range(1, max_attempts + 1):
            try:
                await self._runpod.stop_pod(pod_id)

                break
            except RunPodLaunchError as e:
                if attempt == max_attempts:
                    raise

                logging.warning(
                    "runpod: stop_pod(%s) attempt %d/%d failed: %s — retrying in %ss",
                    pod_id,
                    attempt,
                    max_attempts,
                    e,
                    delay,
                )

                await asyncio.sleep(delay)
                delay *= 2

    async def _shutdown_pod(self) -> None:
        pod_id = self._pod_handle.pod_id

        if self._runtime_config.terminate_on_down:
            await self._runpod.terminate_pod(pod_id)

            logging.info("runpod: pod %s terminated", pod_id)

            self._pod_handle = None
        else:
            try:
                await self._stop_pod(pod_id)
            except RunPodLaunchError as e:
                # `model-compose down` is explicit; surface the failure so the
                # operator stops the pod from the dashboard before it burns a
                # shift's worth of GPU time.
                logging.error("runpod: shutdown stop_pod(%s) failed: %s", pod_id, e)
                raise

            logging.info("runpod: pod %s stopped (volume preserved)", pod_id)

    # ------------------------------------------------------------------
    # Idle timer
    # ------------------------------------------------------------------

    def _schedule_idle_timer(self) -> None:
        if self._idle_timeout <= 0:
            return

        self._idle_timer_task = asyncio.create_task(
            self._idle_timer_callback(),
            name=f"runpod-idle-timer:{self.worker_id}",
        )

    def _cancel_idle_timer(self) -> None:
        task = self._idle_timer_task
        self._idle_timer_task = None

        if task is not None and not task.done():
            task.cancel()

    async def _idle_timer_callback(self) -> None:
        try:
            await asyncio.sleep(self._idle_timeout)
        except asyncio.CancelledError:
            return

        if self._active_requests > 0:
            return

        logging.info(
            "runpod: component '%s' idle for %ss, stopping pod",
            self.worker_id,
            self._idle_timeout,
        )

        if self._proxy is not None:
            try:
                await asyncio.wait_for(self._proxy.stop(), timeout=self._stop_timeout)
            except asyncio.TimeoutError:
                logging.warning("runpod: proxy stop timed out, forcing pod stop anyway")
            except Exception as e:
                logging.warning("runpod: proxy stop raised: %s", e)

            self._proxy = None
            self._channel = None

        if self._pod_handle is not None:
            pod_id = self._pod_handle.pod_id
            try:
                await self._stop_pod(pod_id)
            except RunPodLaunchError as e:
                # Idle path is background; no operator is waiting on the
                # result. Log loud so the pod_id ends up in the ops log for
                # manual cleanup from the RunPod dashboard.
                logging.error(
                    "runpod: idle stop_pod(%s) failed after retries — manual intervention required: %s",
                    pod_id,
                    e,
                )

    async def _reclaim_orphan_pods(self) -> None:
        """Terminate any pods on the account whose name matches this
        component. Called from `start()` so a crash + restart cannot leave
        GPU time billing in the background.
        """
        pods = await self._runpod.get_pods()
        orphans = [ pod for pod in pods if pod.get("name") == self._pod_name ]

        if not orphans:
            return

        logging.warning(
            "runpod: component '%s' has %d orphan pod(s) from a previous session — terminating",
            self.worker_id,
            len(orphans),
        )

        for pod in orphans:
            pod_id = pod.get("id")

            if not pod_id:
                continue

            try:
                await self._runpod.terminate_pod(pod_id)
                logging.info("runpod: orphan pod %s terminated", pod_id)
            except Exception as e:
                # SDK's terminate_pod already swallows; this is best-effort
                # on top. A still-living orphan after this will keep billing,
                # so log loudly for the operator.
                logging.error("runpod: failed to terminate orphan pod %s: %s", pod_id, e)

    @staticmethod
    def _build_pod_bootstrap(worker_port: int) -> str:
        """Shell command run as the pod's docker CMD. Installs model-compose
        from git (pip skips when the install is already satisfied in the pip
        cache) then execs the WS worker.

        The network volume is mounted at ``/workspace`` by default; pip cache
        lives there so re-launches after a stop skip the download.
        """
        return (
            "bash -lc '"
            f"mkdir -p {_POD_PIP_CACHE_DIR} && "
            f"PIP_CACHE_DIR={_POD_PIP_CACHE_DIR} "
            f"pip install --upgrade \"git+{_POD_GIT_REMOTE}@{_POD_GIT_REVISION}\" && "
            f"exec python -m {_POD_WORKER_MODULE} --port {worker_port}"
            "'"
        )

def _worker_factory(message: IpcMessage, websocket: Any) -> ComponentRunPodRuntimeWorker:
    payload = IpcStartPayload.model_validate(message.payload or {})

    return ComponentRunPodRuntimeWorker(
        payload.component_id,
        payload.component_config,
        payload.global_configs,
        websocket,
    )

def main() -> None:
    """Entrypoint when launched as `python -m mindor.core.component.runtime.runpod`.

    Starts an `IpcWsServerChannel` that waits for the parent manager's WS
    connection, performs the START handshake, and drives a
    `ComponentRunPodRuntimeWorker` over that channel.
    """
    parser = argparse.ArgumentParser(prog="mindor-runpod-worker")
    parser.add_argument("--port", type=int, default=int(os.environ.get("WORKER_PORT", "8000")))
    parser.add_argument("--host", type=str, default="0.0.0.0")
    args = parser.parse_args()

    auth_token = os.environ.get("WORKER_AUTH_TOKEN")

    if not auth_token:
        # Hard-fail: without the shared secret the WS endpoint is open to the
        # internet via the RunPod proxy URL. Refuse to serve rather than
        # expose an unauthenticated inference backend.
        print("runpod: WORKER_AUTH_TOKEN env is required", file=sys.stderr)
        sys.exit(2)

    channel = IpcWsServerChannel(
        _worker_factory,
        auth_token=auth_token,
        host=args.host,
        port=args.port,
    )

    asyncio.run(channel.serve())

if __name__ == "__main__":
    main()
