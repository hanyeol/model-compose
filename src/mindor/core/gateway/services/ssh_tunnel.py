from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Iterator, Any
from mindor.dsl.schema.gateway import SshTunnelGatewayConfig, SshConnectionConfig, SshAuthConfig
from mindor.core.utils.ssh_client import SshClient, SshConnectionParams, SshAuthParams, SshKeyfileAuthParams, SshPasswordAuthParams
from mindor.core.utils.time import parse_duration
from mindor.core.logger import logging
from ..base import GatewayService, GatewayType, register_gateway
import asyncio

if TYPE_CHECKING:
    pass

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
        """Establish SSH tunnel and start remote port forwarding"""
        logging.info(
            f"Establishing SSH tunnel to {self.config.connection.host}:{self.config.connection.port}"
        )

        self._shutdown_event = asyncio.Event()

        self.client = SshClient(self._build_connection_params(self.config.connection))
        await self.client.connect()

        # Start remote port forwarding for each port mapping
        for remote_port, local_host, local_port in self.config.port:
            actual_remote_port = await self.client.start_remote_port_forwarding(
                remote_port=remote_port,
                local_port=local_port,
                local_host=local_host
            )

            self.ports[local_port] = actual_remote_port

            logging.info(
                f"Remote port forwarding started: {self.config.connection.host}:{remote_port} -> {local_host}:{local_port}"
            )

        # Keep the SSH connection alive until shutdown event is set
        await self._shutdown_event.wait()

    def _build_connection_params(self, config: SshConnectionConfig) -> SshConnectionParams:
        return SshConnectionParams(
            host=config.host,
            port=config.port,
            auth=self._build_auth_params(config.auth),
            keepalive_interval=int(parse_duration(config.keepalive_interval).total_seconds())
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

    async def _shutdown(self) -> None:
        """Stop SSH tunnel and cleanup"""
        # Signal the _serve task to stop
        if self._shutdown_event:
            self._shutdown_event.set()

        if self.client:
            logging.info(
                f"Stopping SSH tunnel to {self.config.connection.host}:{self.config.connection.port}"
            )

            await self.client.close()
            self.client = None
            self.ports = {}
            self._shutdown_event = None
