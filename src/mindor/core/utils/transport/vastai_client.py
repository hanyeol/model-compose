from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
import asyncio

# Transient statuses — reaching one of these before `running` is a launch failure.
_TERMINAL_STATUSES = { "exited", "offline" }

# Cloud-tier enum value → Vast `search_offers` query fragments. `datacenter=true`
# is strictly narrower than `verified=true`, so DATACENTER adds both filters to
# force the intersection; UNVERIFIED is peer-hosted only; ALL skips the filter
# entirely and leans on the host reliability score instead.
_CLOUD_TYPE_QUERY = {
    "DATACENTER": "verified=true datacenter=true",
    "VERIFIED":   "verified=true",
    "UNVERIFIED": "verified=false",
    "ALL":        "",
}

class VastaiError(RuntimeError):
    """Raised on any Vast.ai client failure (API error, timeout, instance
    reached terminal status, no offers matched, quota exhausted)."""

@dataclass
class VastaiClientParams:
    """Primitive view of the config this client needs. Higher layers that
    hold a richer DSL schema object translate it into this dataclass so the
    transport layer stays DSL-agnostic."""
    api_key: str
    gpu_type: str
    gpu_count: int
    cloud_type: str
    max_price: Optional[float]
    container_disk_gb: int
    network_volume_id: Optional[int]
    volume_mount_path: str
    worker_port: int
    start_timeout: float

class VastaiClient:
    """Async client over the (synchronous) `vastai` SDK.

    Every method wraps the SDK call in `asyncio.to_thread` so the event loop
    stays responsive during multi-minute instance provisioning. Error policy
    is transparent: SDK failures surface as ``VastaiError`` on every method.
    Callers that want to tolerate best-effort failures wrap the call in
    their own try/except.
    """
    def __init__(self, params: VastaiClientParams):
        self.params: VastaiClientParams = params

        self._sdk = None

    async def create_instance(
        self,
        label: str,
        image: str,
        env: Dict[str, str],
        onstart_cmd: Optional[str] = None,
    ) -> str:
        """Pick the cheapest matching offer and rent it. Returns the instance
        id. Does not wait for RUNNING — callers that need the running instance
        call ``wait_until_running`` next."""
        offer_id = await self._select_cheapest_offer()

        try:
            instance = await asyncio.to_thread(
                self._get_sdk().create_instance,
                id=offer_id,
                image=image,
                disk=self.params.container_disk_gb,
                env=self._encode_env(env, exposed_ports=[self.params.worker_port]),
                label=label,
                onstart_cmd=onstart_cmd,
                link_volume=self.params.network_volume_id,
                mount_path=self.params.volume_mount_path if self.params.network_volume_id else None,
                # Vast's SDK forces us to pick a runtype (ssh/jupyter/args).
                # `ssh` is what we want: Vast writes `onstart_cmd` verbatim to
                # /root/onstart.sh and bashes it after the container is up.
                # The `args` runtype would instead treat `onstart_cmd` as the
                # literal `exec` argv — our multi-line bootstrap script would
                # be fed as a single argv[0] and the container would fail with
                # an OCI runtime error on `exec: "bash -lc '..."`.
                ssh=True,
            )
        except Exception as e:
            raise VastaiError(f"create_instance failed: {e}") from e

        instance_id = instance.get("new_contract") or instance.get("id")

        if instance_id is None:
            raise VastaiError(f"create_instance returned no instance id: {instance}")

        return str(instance_id)

    async def stop_instance(self, instance_id: str) -> None:
        """Stop (pause) a running instance. Resumable via ``start_instance``."""
        try:
            await asyncio.to_thread(self._get_sdk().stop_instance, id=instance_id)
        except Exception as e:
            raise VastaiError(f"stop_instance({instance_id}) failed: {e}") from e

    async def start_instance(self, instance_id: str) -> None:
        """Resume a previously stopped instance. Does not wait for RUNNING."""
        try:
            await asyncio.to_thread(self._get_sdk().start_instance, id=instance_id)
        except Exception as e:
            raise VastaiError(f"start_instance({instance_id}) failed: {e}") from e

    async def destroy_instance(self, instance_id: str) -> None:
        """Permanently delete an instance."""
        try:
            await asyncio.to_thread(self._get_sdk().destroy_instance, id=instance_id)
        except Exception as e:
            raise VastaiError(f"destroy_instance({instance_id}) failed: {e}") from e

    async def get_instance(self, instance_id: str) -> Optional[Dict[str, Any]]:
        try:
            return await asyncio.to_thread(self._get_sdk().show_instance, id=instance_id)
        except Exception as e:
            raise VastaiError(f"get_instance({instance_id}) failed: {e}") from e

    async def get_instances(self) -> List[Dict[str, Any]]:
        """List instances on the account; used for discovering orphans by label."""
        try:
            return await asyncio.to_thread(self._get_sdk().show_instances) or []
        except Exception as e:
            raise VastaiError(f"get_instances failed: {e}") from e

    async def get_volume(self, volume_id: int) -> Optional[Dict[str, Any]]:
        """Return the owned volume row matching ``volume_id``, or ``None`` when
        no such volume exists on the account. Vast's SDK has no single-volume
        lookup, so this filters the full ``show_volumes`` list."""
        try:
            volumes = await asyncio.to_thread(self._get_sdk().show_volumes) or []
        except Exception as e:
            raise VastaiError(f"get_volume({volume_id}) failed: {e}") from e

        for volume in volumes:
            if volume.get("id") == volume_id:
                return volume

        return None

    async def wait_until_running(self, instance_id: str) -> Dict[str, Any]:
        """Poll ``get_instance`` until the instance reaches ``running``.
        Destroys the instance on timeout so a stuck provisioning instance
        does not leak budget."""
        loop = asyncio.get_event_loop()
        deadline = loop.time() + self.params.start_timeout
        poll_interval = 5.0

        while True:
            # Transient API errors during polling shouldn't abort provisioning —
            # treat them as "unknown status" and try again next cycle.
            try:
                instance = await self.get_instance(instance_id)
            except VastaiError:
                instance = None

            if instance is not None:
                status = instance.get("actual_status")

                if status == "running":
                    return instance

                if status in _TERMINAL_STATUSES:
                    raise VastaiError(f"instance {instance_id} reached terminal status {status}")

            if loop.time() > deadline:
                try:
                    await self.destroy_instance(instance_id)
                except VastaiError:
                    pass

                raise VastaiError(
                    f"instance {instance_id} did not reach running within start_timeout ({self.params.start_timeout}s)"
                )

            await asyncio.sleep(poll_interval)

    def extract_port_mapping(self, instance: Dict[str, Any], container_port: int) -> Tuple[str, int]:
        """Resolve ``(public_host, public_port)`` for the given container port
        from a running instance row. Vast exposes a Docker-style ``ports`` dict
        keyed by ``{container_port}/tcp`` listing the host-side mapping; the
        public hostname lives in a separate ``public_ipaddr`` field."""
        host = instance.get("public_ipaddr")

        if not host:
            raise VastaiError(f"instance {instance.get('id')} has no public_ipaddr")

        ports = instance.get("ports") or {}
        mapping = ports.get(f"{container_port}/tcp")

        if not mapping:
            raise VastaiError(
                f"instance {instance.get('id')} has no host mapping for container port {container_port}"
            )

        host_port = mapping[0].get("HostPort")

        if not host_port:
            raise VastaiError(
                f"instance {instance.get('id')} host mapping for container port {container_port} is missing HostPort"
            )

        return str(host).strip(), int(host_port)

    def _get_sdk(self):
        """Instantiate the Vast SDK on first use. Each `VastaiClient` owns its
        own `VastAI(...)` — Vast's SDK is instance-scoped (no module-global
        api_key), so distinct clients can coexist without serialization."""
        if self._sdk is None:
            import vastai

            self._sdk = vastai.VastAI(api_key=self.params.api_key)

        return self._sdk

    async def _select_cheapest_offer(self) -> int:
        """Query the marketplace for the cheapest offer that satisfies the
        requested GPU type / count / cloud tier / price ceiling. When a
        network volume is configured, the search is additionally pinned to
        that volume's host — Vast volumes are machine-local, so the only
        offers that can link the volume are the ones on the same machine."""
        query_parts = [
            f"gpu_name={self._encode_gpu_type(self.params.gpu_type)}",
            f"num_gpus={self.params.gpu_count}",
            "rentable=true",
        ]

        cloud_type_fragment = _CLOUD_TYPE_QUERY.get(self.params.cloud_type, "")

        if cloud_type_fragment:
            query_parts.append(cloud_type_fragment)

        if self.params.max_price is not None:
            query_parts.append(f"dph_total<={self.params.max_price}")

        if self.params.network_volume_id is not None:
            machine_id = await self._resolve_volume_machine_id(self.params.network_volume_id)
            query_parts.append(f"machine_id={machine_id}")

        query = " ".join(query_parts)

        try:
            offers = await asyncio.to_thread(
                self._get_sdk().search_offers,
                query=query,
                order="dph_total",
                no_default=True,
            )
        except Exception as e:
            raise VastaiError(f"search_offers failed: {e}") from e

        if not offers:
            raise VastaiError(f"no offers matched query '{query}'")

        return int(offers[0]["id"])

    async def _resolve_volume_machine_id(self, volume_id: int) -> int:
        """Look up a volume and return the ``machine_id`` it lives on.
        Only ``creating`` is treated as fatal here — ``in-use`` can mean an
        orphan instance from a previous session still holds the link, which
        Vast's own ``create_instance`` call will surface with a clearer error
        than we can guess at here."""
        volume = await self.get_volume(volume_id)

        if volume is None:
            raise VastaiError(
                f"network_volume_id {volume_id} is not visible on this account; "
                f"check the ID or create a volume with `vastai create volume`"
            )

        status = volume.get("status")

        if status == "creating":
            raise VastaiError(
                f"network_volume_id {volume_id} is still provisioning; wait for it to reach 'created' and retry"
            )

        machine_id = volume.get("machine_id")

        if machine_id is None:
            raise VastaiError(f"network_volume_id {volume_id} has no machine_id in its record")

        return int(machine_id)

    @staticmethod
    def _encode_gpu_type(gpu_type: str) -> str:
        """Vast's search query grammar is whitespace-split, so GPU names with
        spaces (``RTX 4090``, ``H100 SXM``) must have their spaces replaced
        with underscores to be parsed as a single token."""
        return gpu_type.replace(" ", "_")

    @staticmethod
    def _encode_env(env: Dict[str, str], exposed_ports: List[int]) -> str:
        """Vast's SDK accepts the `env` field as a single CLI-style string of
        ``-e KEY=VALUE`` and ``-p N:N`` tokens — the port tokens are how the
        container's EXPOSE list is extended beyond whatever the image declares,
        so the Vast host port mapping actually gets created for ``worker_port``."""
        env_tokens = [f"-e {key}={value}" for key, value in env.items()]
        port_tokens = [f"-p {port}:{port}" for port in exposed_ports]

        return " ".join(env_tokens + port_tokens)
