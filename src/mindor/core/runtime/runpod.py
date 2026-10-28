from __future__ import annotations

from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from mindor.dsl.schema.runtime import RunPodRuntimeConfig
from mindor.core.foundation.variable.time import parse_time
from mindor.core.logger import logging
import asyncio

# Terminal pod states — reaching one of these before RUNNING is a launch failure.
_TERMINAL_STATUSES = { "EXITED", "ERROR", "TERMINATED", "FAILED" }

# The `runpod` SDK stores credentials on the module (`runpod.api_key`) and
# pod lifecycle calls (create/stop/resume/terminate) read that module
# attribute unconditionally. Serialize set-then-call across managers so two
# configs with different keys cannot clobber each other mid-request.
_api_key_lock: asyncio.Lock = asyncio.Lock()

class RunPodLaunchError(RuntimeError):
    """Raised when pod provisioning fails (quota, out-of-stock, timeout, API error)."""

@dataclass
class RunPodHandle:
    """Lightweight pointer to a provisioned RunPod pod."""
    pod_id: str
    status: str
    worker_port: int
    cost_per_hr: Optional[float]
    raw: Dict[str, Any]

    @property
    def proxy_ws_url(self) -> str:
        return f"wss://{self.pod_id}-{self.worker_port}.proxy.runpod.net"

    @property
    def proxy_http_url(self) -> str:
        return f"https://{self.pod_id}-{self.worker_port}.proxy.runpod.net"

class RunPodRuntime:
    """Async facade over the (synchronous) `runpod` SDK for pod lifecycle.

    Every method wraps the SDK call in `asyncio.to_thread` so model-compose's
    event loop stays responsive during multi-minute pod provisioning.
    """
    def __init__(self, config: RunPodRuntimeConfig):
        self.config: RunPodRuntimeConfig = config

    async def create_pod(
        self,
        *,
        name: str,
        image: str,
        env: Dict[str, str],
        docker_args: Optional[str] = None,
    ) -> RunPodHandle:
        """Create a pod, poll until RUNNING, return a handle with the proxy URL."""
        import runpod

        config = self.config

        # `create_pod` and the stop/resume/terminate/get calls read the key
        # from the module-level `runpod.api_key`; they do not accept per-call
        # api_key kwargs. Set it right before dispatch under a lock so two
        # managers with distinct keys can coexist in one process.
        async with _api_key_lock:
            runpod.api_key = config.api_key

            try:
                pod = await asyncio.to_thread(
                    runpod.create_pod,
                    name=name,
                    image_name=image,
                    gpu_type_id=config.gpu_type,
                    gpu_count=config.gpu_count,
                    cloud_type=config.cloud_type,
                    data_center_id=config.data_center_id,
                    container_disk_in_gb=config.container_disk_gb,
                    network_volume_id=config.network_volume_id,
                    volume_mount_path=config.volume_mount_path,
                    ports=f"{config.worker_port}/http",
                    env=env,
                    docker_args=docker_args,
                    start_ssh=False,
                )
            except Exception as e:
                raise RunPodLaunchError(f"create_pod failed: {e}") from e

        pod_id = pod["id"]
        logging.info("runpod: created pod %s, waiting for RUNNING...", pod_id)

        return await self._wait_until_running(pod_id)

    async def stop_pod(self, pod_id: str) -> None:
        """Stop (pause) a running pod. Resumable via `resume_pod`.

        Raises `RunPodLaunchError` on API failure so callers can decide
        whether to retry — leaving a pod running quietly is a billing hazard.
        """
        import runpod

        async with _api_key_lock:
            runpod.api_key = self.config.api_key

            try:
                await asyncio.to_thread(runpod.stop_pod, pod_id)
            except Exception as e:
                raise RunPodLaunchError(f"stop_pod({pod_id}) failed: {e}") from e

    async def resume_pod(self, pod_id: str) -> RunPodHandle:
        """Resume a previously stopped pod; polls until RUNNING."""
        import runpod

        async with _api_key_lock:
            runpod.api_key = self.config.api_key

            try:
                await asyncio.to_thread(runpod.resume_pod, pod_id)
            except Exception as e:
                raise RunPodLaunchError(f"resume_pod({pod_id}) failed: {e}") from e

        logging.info("runpod: resuming pod %s, waiting for RUNNING...", pod_id)

        return await self._wait_until_running(pod_id)

    async def terminate_pod(self, pod_id: str) -> None:
        """Permanently delete a pod. Idempotent in effect — swallows errors."""
        import runpod

        async with _api_key_lock:
            runpod.api_key = self.config.api_key

            try:
                await asyncio.to_thread(runpod.terminate_pod, pod_id)
            except Exception as e:
                logging.warning("runpod: terminate_pod(%s) failed: %s", pod_id, e)

    async def get_pod(self, pod_id: str) -> Optional[Dict[str, Any]]:
        import runpod

        async with _api_key_lock:
            runpod.api_key = self.config.api_key

            try:
                return await asyncio.to_thread(runpod.get_pod, pod_id)
            except Exception as e:
                logging.warning("runpod: get_pod(%s) failed: %s", pod_id, e)
                return None

    async def get_pods(self) -> List[Dict[str, Any]]:
        """List pods on the account; used for discovering orphan pods by name
        after a parent-process crash or restart. Returns an empty list on
        failure rather than propagating — recovery is best-effort."""
        import runpod

        async with _api_key_lock:
            runpod.api_key = self.config.api_key

            try:
                pods = await asyncio.to_thread(runpod.get_pods)
                return pods or []
            except Exception as e:
                logging.warning("runpod: get_pods failed: %s", e)
                return []

    async def _wait_until_running(self, pod_id: str) -> RunPodHandle:
        deadline = asyncio.get_event_loop().time() + parse_time(self.config.start_timeout)
        poll_interval = 5.0

        while True:
            pod = await self.get_pod(pod_id)

            if pod is None:
                raise RunPodLaunchError(f"pod {pod_id} not found during polling")

            # REST v2 exposes `desiredStatus`; the legacy GraphQL path sometimes
            # only populates `status`. Fall back so this works on both.
            status = pod.get("desiredStatus") or pod.get("status")

            if status == "RUNNING":
                return self._build_handle(pod_id, pod)

            if status in _TERMINAL_STATUSES:
                raise RunPodLaunchError(f"pod {pod_id} reached terminal status {status}")

            if asyncio.get_event_loop().time() > deadline:
                # Best-effort cleanup so a stuck PROVISIONING pod does not leak budget.
                await self.terminate_pod(pod_id)

                raise RunPodLaunchError(
                    f"pod {pod_id} did not reach RUNNING within start_timeout ({self.config.start_timeout})"
                )

            await asyncio.sleep(poll_interval)

    def _build_handle(self, pod_id: str, pod: Dict[str, Any]) -> RunPodHandle:
        cost = pod.get("costPerHr")

        if isinstance(cost, str):
            try:
                cost = float(cost)
            except ValueError:
                cost = None

        return RunPodHandle(
            pod_id=pod_id,
            status="RUNNING",
            worker_port=self.config.worker_port,
            cost_per_hr=cost,
            raw=pod,
        )
