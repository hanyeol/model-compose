from __future__ import annotations

from typing import Any, Dict, Optional
from mindor.dsl.schema.runtime import RunPodRuntimeConfig
from mindor.core.foundation.variable.time import parse_time
from mindor.core.utils.transport.runpod_client import RunPodClient, RunPodClientParams
from mindor.core.logger import logging
from .common import CommonRuntime

class RunPodRuntime(CommonRuntime):
    """Lifecycle wrapper around a single RunPod GPU pod.

    Mirrors the shape of ``LocalVirtualEnvRuntime`` / ``LocalProcessRuntime`` /
    ``DockerContainer``: the instance owns one pod and exposes
    ``create`` / ``start`` / ``stop`` / ``remove`` for its lifecycle.
    Knows nothing about IPC — callers that talk to a worker inside the pod
    open their own transport (typically a WebSocket to the RunPod proxy URL).
    """
    config: RunPodRuntimeConfig

    def __init__(
        self,
        worker_id: str,
        config: RunPodRuntimeConfig,
        verbose: bool = False,
    ):
        super().__init__(config, verbose)

        self.worker_id = worker_id

        self._client: RunPodClient = RunPodClient(self._build_client_params(config))
        self._pod_id: Optional[str] = None
        self._pod: Optional[Dict[str, Any]] = None

    @property
    def pod_name(self) -> str:
        """RunPod ``name`` field used both to tag new pods and to claim existing ones."""
        return f"mindor-{self.worker_id}"

    @property
    def pod_id(self) -> Optional[str]:
        return self._pod_id

    @property
    def proxy_websocket_url(self) -> str:
        return f"wss://{self._pod_id}-{self.config.worker_port}.proxy.runpod.net"

    @property
    def proxy_http_url(self) -> str:
        return f"https://{self._pod_id}-{self.config.worker_port}.proxy.runpod.net"

    @property
    def cost_per_hr(self) -> Optional[float]:
        cost = self._pod.get("costPerHr") if self._pod is not None else None

        if isinstance(cost, str):
            try:
                return float(cost)
            except ValueError:
                return None

        return cost

    async def create(
        self,
        image: str,
        env: Dict[str, str],
        docker_args: Optional[str] = None,
    ) -> None:
        """Create the pod and wait until RUNNING. Idempotent only across
        a crash + ``cleanup_orphans``; callers must not call twice on the
        same instance."""
        self._pod_id = await self._client.create_pod(
            name=self.pod_name,
            image=image,
            env=env,
            docker_args=docker_args,
        )
        self._pod = await self._client.wait_until_running(self._pod_id)

        logging.info("runpod: pod %s created (cost=%s/hr)", self._pod_id, self.cost_per_hr)

    async def claim(self, pod_id: str) -> bool:
        """Claim the pod identified by ``pod_id`` (set ``self._pod_id``
        without touching the cloud) so a reconnect skips the create cost.
        Returns False when the pod is no longer discoverable on the account —
        the caller then falls back to ``create``."""
        try:
            pod = await self._client.get_pod(pod_id)
        except Exception:
            return False

        if pod is None:
            return False

        self._pod_id = pod_id
        self._pod = pod

        logging.info("runpod: pod %s claimed", self._pod_id)

        return True

    async def start(self) -> None:
        """Resume the pod from STOPPED → RUNNING. No-op when the pod is
        already RUNNING. Re-queries the account before deciding so manual
        state changes made via the RunPod console (stop/resume between
        sessions) are picked up — `resume_pod` on an already running pod
        can error on some RunPod backends."""
        self._pod = await self._client.get_pod(self._pod_id)

        if self._is_running(self._pod):
            return

        await self._client.resume_pod(self._pod_id)
        self._pod = await self._client.wait_until_running(self._pod_id)

        logging.info("runpod: pod %s resumed (cost=%s/hr)", self._pod_id, self.cost_per_hr)

    async def stop(self) -> None:
        """Stop the pod (resumable later via ``start``)."""
        await self._client.stop_pod(self._pod_id)
        self._pod = await self._client.get_pod(self._pod_id)

        logging.info("runpod: pod %s stopped", self._pod_id)

    async def remove(self) -> None:
        """Terminate (permanently delete) the pod."""
        await self._client.terminate_pod(self._pod_id)

        logging.info("runpod: pod %s terminated", self._pod_id)

        self._pod_id = None
        self._pod = None

    @staticmethod
    def _build_client_params(config: RunPodRuntimeConfig) -> RunPodClientParams:
        return RunPodClientParams(
            api_key=config.api_key,
            gpu_type=config.gpu_type,
            gpu_count=config.gpu_count,
            cloud_type=config.cloud_type,
            data_center_id=config.data_center_id,
            container_disk_gb=config.container_disk_gb,
            network_volume_id=config.network_volume_id,
            volume_mount_path=config.volume_mount_path,
            worker_port=config.worker_port,
            start_timeout=parse_time(config.start_timeout),
        )

    @staticmethod
    def _is_running(pod: Dict[str, Any]) -> bool:
        status = pod.get("desiredStatus") or pod.get("status")

        return status == "RUNNING"
