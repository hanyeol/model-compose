from __future__ import annotations

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Iterator, Any
from mindor.dsl.schema.gateway import SshTunnelGatewayConfig, SshConnectionConfig, SshAuthConfig
from mindor.core.utils.ssh_client import SshClient, SshConnectionParams, SshAuthParams, SshKeyfileAuthParams, SshPasswordAuthParams
from mindor.core.utils.time import parse_duration
from mindor.core.logger import logging
from ..base import GatewayService, GatewayType, register_gateway
import asyncio

@register_gateway(GatewayType.SSH_TUNNEL)
class SshTunnelGateway(GatewayService):
    def __init__(self, id: str, config: SshTunnelGatewayConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.client: Optional[SshClient] = None
        self.ports: Dict[int, int] = {}  # {local_port: remote_port}
        self._shutdown_event: Optional[asyncio.Event] = None

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return [ "paramiko" ]

    def get_context(self, port: int) -> Optional[Dict[str, Any]]:
        remote_port = self.ports.get(port)
 
        if remote_port is not None:
            return {
                "public_address": f"{self.config.connection.host}:{remote_port}"
            }
 
        return None

    def serves_port(self, port: int) -> bool:
        return port in self.ports

    async def _serve(self) -> None:
        watch_interval = parse_duration(self.config.connection.watch_interval)
        retry_interval = parse_duration(self.config.connection.retry_interval)

        self._shutdown_event = asyncio.Event()
        retry_count = 0

        while not self._shutdown_event.is_set():
            try:
                await self._establish_tunnel(self.config.connection, self.config.port)
                retry_count = 0

                while not self._shutdown_event.is_set():
                    if not self.client or not self.client.is_connected():
                        raise ConnectionError("SSH connection lost")

                    await self._wait_for_shutdown(self._shutdown_event, timeout=watch_interval)
            except Exception as e:
                if self._shutdown_event.is_set():
                    break

                await self._reset_connection()
                retry_count += 1

                if self.config.connection.max_retry_count > 0 and retry_count > self.config.connection.max_retry_count:
                    logging.error(f"SSH max retry count ({self.config.connection.max_retry_count}) reached. Giving up.")
                    break

                logging.warning(f"SSH connection lost: {e}. Reconnecting in {retry_interval}s... (attempt {retry_count})")

                if await self._wait_for_shutdown(self._shutdown_event, retry_interval):
                    break

    async def _shutdown(self) -> None:
        if self._shutdown_event:
            self._shutdown_event.set()

        if self.client:
            logging.info(f"Stopping SSH tunnel to {self.config.connection.host}:{self.config.connection.port}")
            await self.client.close()

        self.client = None
        self.ports = {}

    async def _establish_tunnel(self, connection: SshConnectionConfig, forwards: List[List[Union[int, str]]]) -> None:
        logging.info(f"Establishing SSH tunnel to {connection.host}:{connection.port}")

        self.client = SshClient(self._build_connection_params(connection))
        await self.client.connect()

        # Start remote port forwarding for each port mapping
        for remote_port, local_host, local_port in forwards:
            actual_remote_port = await self.client.start_remote_port_forwarding(
                remote_port=remote_port,
                local_port=local_port,
                local_host=local_host
            )

            self.ports[local_port] = actual_remote_port

            logging.info(f"Remote port forwarding started: {connection.host}:{remote_port} -> {local_host}:{local_port}")

    def _build_connection_params(self, config: SshConnectionConfig) -> SshConnectionParams:
        return SshConnectionParams(
            host=config.host,
            port=config.port,
            auth=self._build_auth_params(config.auth),
            keepalive_interval=int(parse_duration(config.keepalive_interval))
        )
    
    def _build_auth_params(self, config: SshAuthConfig) -> SshAuthParams:
        if config.type.value == "keyfile":
            return SshKeyfileAuthParams(
                username=config.username,
                keyfile=config.keyfile
            )
        
        if config.type.value == "password":
            return SshPasswordAuthParams(
                username=config.username,
                password=config.password
            )

        raise ValueError(f"Unknown SSH auth type: {config.type}")

    async def _wait_for_shutdown(self, shutdown_event: asyncio.Event, timeout: float) -> bool:
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    async def _reset_connection(self) -> None:
        if self.client:
            try:
                await self.client.close()
            except Exception as e:
                logging.debug(f"Error closing SSH connection during reset: {e}")

        self.client = None
        self.ports = {}
