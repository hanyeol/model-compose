from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Iterator, Any
from mindor.dsl.schema.gateway import HttpTunnelGatewayConfig
from ..base import CommonHttpTunnelGateway
from mindor.core.logger import logging
import asyncio
import re

if TYPE_CHECKING:
    pass

class CloudflareHttpTunnelGateway(CommonHttpTunnelGateway):
    TUNNEL_URL_PATTERN = re.compile(r"https://[a-zA-Z0-9\-]+\.trycloudflare\.com")
    TUNNEL_READY_TIMEOUT = 30

    def __init__(self, config: HttpTunnelGatewayConfig):
        super().__init__(config)

        self.processes: Optional[Dict[int, asyncio.subprocess.Process]] = None

    async def _serve(self) -> Optional[Dict[int, str]]:
        self.processes = {}
        urls: Dict[int, str] = {}

        for port in self.config.port:
            process = await asyncio.create_subprocess_exec(
                "cloudflared", "tunnel", "--url", f"http://localhost:{port}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            public_url = await self._wait_for_url(process)

            if not public_url:
                raise RuntimeError(
                    f"Failed to obtain Cloudflare tunnel URL for port {port}. "
                    "Ensure 'cloudflared' is installed and accessible in PATH."
                )

            self.processes[port] = process
            urls[port] = public_url

        return urls

    async def _shutdown(self) -> None:
        for process in self.processes.values():
            if process.returncode is None:
                process.terminate()
                try:
                    async with asyncio.timeout(5):
                        await process.wait()
                except TimeoutError:
                    process.kill()
                    await process.wait()

        self.processes = None

    async def _wait_for_url(self, process: asyncio.subprocess.Process) -> Optional[str]:
        try:
            async with asyncio.timeout(self.TUNNEL_READY_TIMEOUT):
                while True:
                    line = await process.stderr.readline()
                    if not line:
                        break

                    decoded = line.decode("utf-8", errors="replace")
                    match = self.TUNNEL_URL_PATTERN.search(decoded)
                    if match:
                        return match.group(0)
        except TimeoutError:
            logging.warning("Timed out waiting for Cloudflare tunnel URL")
            return None
