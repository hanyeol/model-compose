from __future__ import annotations

from typing import Any, Dict, List, Optional
from dataclasses import dataclass
import asyncio

# Terminal pod states — reaching one of these before RUNNING is a launch failure.
_TERMINAL_STATUSES = { "EXITED", "ERROR", "TERMINATED", "FAILED" }

# The `runpod` SDK stores credentials on the module (`runpod.api_key`) and
# pod lifecycle calls (create/stop/resume/terminate) read that module
# attribute unconditionally. Serialize set-then-call across clients so two
# configs with different keys cannot clobber each other mid-request.
_api_key_lock: asyncio.Lock = asyncio.Lock()

class RunPodError(RuntimeError):
    """Raised on any RunPod client failure (API error, timeout, pod reached
    terminal status, quota, out-of-stock)."""

@dataclass
class RunPodClientParams:
    """Primitive view of the config this client needs. Higher layers that
    hold a richer DSL schema object translate it into this dataclass so the
    transport layer stays DSL-agnostic."""
    api_key: str
    gpu_type: str
    gpu_count: int
    cloud_type: str
    data_center_id: Optional[str]
    container_disk_gb: int
    network_volume_id: Optional[str]
    volume_mount_path: str
    worker_port: int
    start_timeout: float

class RunPodClient:
    """Async client over the (synchronous) `runpod` SDK.

    Every method wraps the SDK call in `asyncio.to_thread` so the event loop
    stays responsive during multi-minute pod provisioning. Error policy is
    transparent: SDK failures surface as ``RunPodError`` on every method.
    Callers that want to tolerate best-effort failures wrap the call in
    their own try/except.
    """
    def __init__(self, params: RunPodClientParams):
        self.params: RunPodClientParams = params

    async def create_pod(
        self,
        name: str,
        image: str,
        env: Dict[str, str],
        docker_args: Optional[str] = None,
    ) -> str:
        """Create a pod and return its id. Does not wait for RUNNING —
        callers that need the running pod call ``wait_until_running`` next."""
        import runpod

        # `create_pod` and the stop/resume/terminate/get calls read the key
        # from the module-level `runpod.api_key`; they do not accept per-call
        # api_key kwargs. Set it right before dispatch under a lock so two
        # clients with distinct keys can coexist in one process.
        async with _api_key_lock:
            runpod.api_key = self.params.api_key

            try:
                pod = await asyncio.to_thread(
                    runpod.create_pod,
                    name=name,
                    image_name=image,
                    gpu_type_id=self.params.gpu_type,
                    gpu_count=self.params.gpu_count,
                    cloud_type=self.params.cloud_type,
                    data_center_id=self.params.data_center_id,
                    container_disk_in_gb=self.params.container_disk_gb,
                    network_volume_id=self.params.network_volume_id,
                    volume_mount_path=self.params.volume_mount_path,
                    ports=f"{self.params.worker_port}/http",
                    env=env,
                    docker_args=docker_args,
                    start_ssh=False,
                )
            except Exception as e:
                raise RunPodError(f"create_pod failed: {e}") from e

        return pod["id"]

    async def stop_pod(self, pod_id: str) -> None:
        """Stop (pause) a running pod. Resumable via ``resume_pod``."""
        import runpod

        async with _api_key_lock:
            runpod.api_key = self.params.api_key

            try:
                await asyncio.to_thread(runpod.stop_pod, pod_id)
            except Exception as e:
                raise RunPodError(f"stop_pod({pod_id}) failed: {e}") from e

    async def resume_pod(self, pod_id: str) -> None:
        """Resume a previously stopped pod. Does not wait for RUNNING."""
        import runpod

        async with _api_key_lock:
            runpod.api_key = self.params.api_key

            try:
                await asyncio.to_thread(runpod.resume_pod, pod_id, self.params.gpu_count)
            except Exception as e:
                raise RunPodError(f"resume_pod({pod_id}) failed: {e}") from e

    async def terminate_pod(self, pod_id: str) -> None:
        """Permanently delete a pod."""
        import runpod

        async with _api_key_lock:
            runpod.api_key = self.params.api_key

            try:
                await asyncio.to_thread(runpod.terminate_pod, pod_id)
            except Exception as e:
                raise RunPodError(f"terminate_pod({pod_id}) failed: {e}") from e

    async def get_pod(self, pod_id: str) -> Dict[str, Any]:
        import runpod

        async with _api_key_lock:
            runpod.api_key = self.params.api_key

            try:
                return await asyncio.to_thread(runpod.get_pod, pod_id)
            except Exception as e:
                raise RunPodError(f"get_pod({pod_id}) failed: {e}") from e

    async def get_pods(self) -> List[Dict[str, Any]]:
        """List pods on the account; used for discovering orphans by name."""
        import runpod

        async with _api_key_lock:
            runpod.api_key = self.params.api_key

            try:
                return await asyncio.to_thread(runpod.get_pods) or []
            except Exception as e:
                raise RunPodError(f"get_pods failed: {e}") from e

    async def wait_until_running(self, pod_id: str) -> Dict[str, Any]:
        """Poll ``get_pod`` until the pod reaches RUNNING. Terminates the pod
        on timeout so a stuck PROVISIONING pod does not leak budget."""
        loop = asyncio.get_event_loop()
        deadline = loop.time() + self.params.start_timeout
        poll_interval = 5.0

        while True:
            # Transient API errors during polling shouldn't abort provisioning —
            # treat them as "unknown status" and try again next cycle.
            try:
                pod = await self.get_pod(pod_id)
            except RunPodError:
                pod = None

            if pod is not None:
                # REST v2 exposes `desiredStatus`; the legacy GraphQL path
                # sometimes only populates `status`. Fall back so this works on both.
                status = pod.get("desiredStatus") or pod.get("status")

                if status == "RUNNING":
                    return pod

                if status in _TERMINAL_STATUSES:
                    raise RunPodError(f"pod {pod_id} reached terminal status {status}")

            if loop.time() > deadline:
                try:
                    await self.terminate_pod(pod_id)
                except RunPodError:
                    pass

                raise RunPodError(
                    f"pod {pod_id} did not reach RUNNING within start_timeout ({self.params.start_timeout}s)"
                )

            await asyncio.sleep(poll_interval)
