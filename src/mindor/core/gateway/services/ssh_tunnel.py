from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Iterator, Any
from mindor.dsl.schema.gateway import SshTunnelGatewayConfig
from ..base import GatewayService, GatewayType, register_gateway
from mindor.core.utils.ssh_client import SshClient
from mindor.core.logger import logging

if TYPE_CHECKING:
    pass

@register_gateway(GatewayType.SSH_TUNNEL)
class SshTunnelGateway(GatewayService):
    def __init__(self, id: str, config: SshTunnelGatewayConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.ssh_client: Optional[SshClient] = None
        self.local_ports: List[int] = []
        self.remote_ports: List[int] = []

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return [ "paramiko" ]

    def get_context(self, port: int) -> Optional[Dict[str, Any]]:
        if port in self.local_ports:
            index = self.local_ports.index(port)
            return {
                "public_address": f"{self.config.connection.host}:{self.remote_ports[index]}"
            }
        return None

    def serves_port(self, port: int) -> bool:
        return port in self.local_ports

    async def _serve(self) -> None:
        """Establish SSH tunnel and start remote port forwarding"""
        logging.info(
            f"Establishing SSH tunnel to {self.config.connection.host}:{self.config.connection.port}"
        )

        # Create SSH client
        self.ssh_client = SshClient(self.config.connection)
        await self.ssh_client.connect()

        # Start remote port forwarding for each port mapping
        for remote_port, local_port in self.config.port:
            actual_remote_port = await self.ssh_client.start_remote_port_forwarding(
                remote_port=remote_port,
                local_port=local_port,
                local_host="localhost"
            )

            self.local_ports.append(local_port)
            self.remote_ports.append(actual_remote_port)

            logging.info(
                f"Remote port forwarding started: {self.config.connection.host}:{remote_port} -> localhost:{local_port}"
            )

    async def _shutdown(self) -> None:
        """Stop SSH tunnel and cleanup"""
        if self.ssh_client:
            logging.info(
                f"Stopping SSH tunnel to {self.config.connection.host}:{self.config.connection.port}"
            )

            await self.ssh_client.close()
            self.ssh_client = None
            self.local_ports = []
            self.remote_ports = []
