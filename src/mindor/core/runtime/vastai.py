from __future__ import annotations

from typing import Any, Dict, Optional, Tuple
from mindor.dsl.schema.runtime import VastaiRuntimeConfig
from mindor.core.foundation.variable.time import parse_time
from mindor.core.utils.transport.vastai_client import VastaiClient, VastaiClientParams
from mindor.core.logger import logging
from .common import CommonRuntime

class VastaiRuntime(CommonRuntime):
    """Lifecycle wrapper around a single Vast.ai GPU instance.

    Mirrors the shape of ``RunPodRuntime`` / ``LocalVirtualEnvRuntime`` /
    ``DockerContainer``: the instance owns one Vast.ai instance and exposes
    ``create`` / ``start`` / ``stop`` / ``remove`` for its lifecycle.
    Knows nothing about IPC — callers that talk to a worker inside the
    instance open their own transport (typically a WebSocket to the
    host-side public IP + mapped port).
    """
    config: VastaiRuntimeConfig

    def __init__(
        self,
        worker_id: str,
        config: VastaiRuntimeConfig,
        verbose: bool = False,
    ):
        super().__init__(config, verbose)

        self.worker_id = worker_id

        self._client: VastaiClient = VastaiClient(self._build_client_params(config))
        self._instance_id: Optional[str] = None
        self._instance: Optional[Dict[str, Any]] = None

    @property
    def instance_label(self) -> str:
        """Vast.ai ``label`` field used both to tag new instances and to claim
        existing ones."""
        return f"mindor-{self.worker_id}"

    @property
    def instance_id(self) -> Optional[str]:
        return self._instance_id

    @property
    def proxy_websocket_url(self) -> str:
        host, port = self._client.extract_port_mapping(self._instance, self.config.worker_port)

        return f"ws://{host}:{port}"

    @property
    def proxy_http_url(self) -> str:
        host, port = self._client.extract_port_mapping(self._instance, self.config.worker_port)

        return f"http://{host}:{port}"

    @property
    def cost_per_hr(self) -> Optional[float]:
        cost = self._instance.get("dph_total") if self._instance is not None else None

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
        onstart_cmd: Optional[str] = None,
    ) -> None:
        """Create the instance and wait until running. Idempotent only across
        a crash + ``cleanup_orphans``; callers must not call twice on the
        same instance."""
        self._instance_id = await self._client.create_instance(
            label=self.instance_label,
            image=image,
            env=env,
            onstart_cmd=onstart_cmd,
        )
        self._instance = await self._client.wait_until_running(self._instance_id)

        logging.info("vastai: instance %s created (cost=%s/hr)", self._instance_id, self.cost_per_hr)

    async def claim(self, instance_id: str) -> bool:
        """Claim the instance identified by ``instance_id`` (set
        ``self._instance_id`` without touching the cloud) so a reconnect skips
        the create cost. Returns False when the instance is no longer
        discoverable on the account — the caller then falls back to
        ``create``."""
        try:
            instance = await self._client.get_instance(instance_id)
        except Exception:
            return False

        if instance is None:
            return False

        self._instance_id = instance_id
        self._instance = instance

        logging.info("vastai: instance %s claimed", self._instance_id)

        return True

    async def start(self) -> None:
        """Resume the instance from stopped → running. No-op when the
        instance is already running. Re-queries the account before deciding
        so manual state changes made via the Vast.ai console (stop/resume
        between sessions) are picked up — ``start_instance`` on an already
        running instance can error on some Vast.ai backends."""
        self._instance = await self._client.get_instance(self._instance_id)

        if self._is_running(self._instance):
            return

        await self._client.start_instance(self._instance_id)
        self._instance = await self._client.wait_until_running(self._instance_id)

        logging.info("vastai: instance %s resumed (cost=%s/hr)", self._instance_id, self.cost_per_hr)

    async def stop(self) -> None:
        """Stop the instance (resumable later via ``start``)."""
        await self._client.stop_instance(self._instance_id)
        self._instance = await self._client.get_instance(self._instance_id)

        logging.info("vastai: instance %s stopped", self._instance_id)

    async def remove(self) -> None:
        """Destroy (permanently delete) the instance."""
        await self._client.destroy_instance(self._instance_id)

        logging.info("vastai: instance %s destroyed", self._instance_id)

        self._instance_id = None
        self._instance = None

    @staticmethod
    def _build_client_params(config: VastaiRuntimeConfig) -> VastaiClientParams:
        return VastaiClientParams(
            api_key=config.api_key,
            gpu_type=config.gpu_type,
            gpu_count=config.gpu_count,
            cloud_type=config.cloud_type,
            max_price=config.max_price,
            container_disk_gb=config.container_disk_gb,
            network_volume_id=config.network_volume_id,
            volume_mount_path=config.volume_mount_path,
            worker_port=config.worker_port,
            start_timeout=parse_time(config.start_timeout),
        )

    @staticmethod
    def _is_running(instance: Dict[str, Any]) -> bool:
        return instance.get("actual_status") == "running"
