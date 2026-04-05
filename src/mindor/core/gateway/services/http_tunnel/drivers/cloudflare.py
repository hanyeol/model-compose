from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Iterator, Any
from mindor.dsl.schema.gateway import CloudflareHttpTunnelGatewayConfig
from ..base import CommonHttpTunnelGateway
from mindor.core.logger import logging
from mindor.core.foundation.compat.asyncio import async_timeout
import asyncio
import re
import tempfile
import os

class CloudflareHttpTunnelGateway(CommonHttpTunnelGateway):
    QUICK_TUNNEL_URL_PATTERN = re.compile(r"https://[a-zA-Z0-9\-]+\.trycloudflare\.com")
    TUNNEL_READY_TIMEOUT = 30

    def __init__(self, config: CloudflareHttpTunnelGatewayConfig):
        super().__init__(config)

        self.processes: Optional[Dict[int, asyncio.subprocess.Process]] = None

    async def _serve(self) -> Optional[Dict[int, str]]:
        self.processes = {}

        if bool(self.config.token or self.config.tunnel):
            return await self._serve_named_tunnel()
        else:
            return await self._serve_quick_tunnel()

    async def _shutdown(self) -> None:
        if self.processes:
            await self._terminate_processes(self.processes)

        self.processes = None

    async def _serve_quick_tunnel(self) -> Dict[int, str]:
        urls: Dict[int, str] = {}

        for port in self.config.port:
            process = await asyncio.create_subprocess_exec(
                "cloudflared", "tunnel", "--url", f"http://localhost:{port}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            public_url = await self._wait_for_quick_tunnel_url(process)

            if not public_url:
                raise RuntimeError(
                    f"Failed to obtain Cloudflare tunnel URL for port {port}. "
                    "Ensure 'cloudflared' is installed and accessible in PATH."
                )

            self.processes[port] = process
            urls[port] = public_url

        return urls

    async def _wait_for_quick_tunnel_url(self, process: asyncio.subprocess.Process) -> Optional[str]:
        try:
            async with async_timeout(self.TUNNEL_READY_TIMEOUT):
                while True:
                    line = await process.stderr.readline()
                    if not line:
                        break

                    decoded = line.decode("utf-8", errors="replace")
                    match = self.QUICK_TUNNEL_URL_PATTERN.search(decoded)
                    if match:
                        return match.group(0)
        except TimeoutError:
            logging.warning("Timed out waiting for Cloudflare tunnel URL")
            return None

    async def _serve_named_tunnel(self) -> Dict[int, str]:
        process = await asyncio.create_subprocess_exec(
            *self._build_named_tunnel_command(),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        await self._wait_for_named_tunnel_ready(process)

        for port in self.config.port:
            self.processes[port] = process

        return self._resolve_named_tunnel_urls()

    def _build_named_tunnel_command(self) -> List[str]:
        if self.config.tunnel:
            config = self._build_named_tunnel_config(self.config.tunnel, self.config.credentials_file)

            fd, path = tempfile.mkstemp(suffix=".yml", prefix="cloudflared-")
            with os.fdopen(fd, "w") as f:
                f.write(config)

            return [ "cloudflared", "tunnel", "--config", path, "run", self.config.tunnel ]

        return [ "cloudflared", "tunnel", "run", "--token", self.config.token ]

    def _build_named_tunnel_config(self, tunnel: str, credentials_file: str) -> str:
        hostname = self.config.hostname

        lines = [
            f"tunnel: {tunnel}",
            f"credentials-file: {credentials_file}",
            "ingress:",
        ]

        for port in self.config.port:
            if hostname:
                lines.append(f"  - hostname: {hostname}")
                lines.append(f"    service: http://localhost:{port}")
            else:
                lines.append(f"  - service: http://localhost:{port}")

        lines.append("  - service: http_status:404")

        return "\n".join(lines) + "\n"

    def _resolve_named_tunnel_urls(self) -> Dict[int, str]:
        if self.config.hostname:
            base_url = f"https://{self.config.hostname}"
        else:
            base_url = f"https://{self.config.tunnel}.cfargotunnel.com"

        return { port: base_url for port in self.config.port }

    async def _wait_for_named_tunnel_ready(self, process: asyncio.subprocess.Process) -> None:
        try:
            async with async_timeout(self.TUNNEL_READY_TIMEOUT):
                while True:
                    line = await process.stderr.readline()
                    if not line:
                        break

                    decoded = line.decode("utf-8", errors="replace")
                    if "Registered tunnel connection" in decoded:
                        return
        except TimeoutError:
            raise RuntimeError(
                "Timed out waiting for Cloudflare named tunnel to become ready. "
                "Check your token or credentials configuration."
            )

    async def _terminate_processes(self, processes: Dict[int, asyncio.subprocess.Process]) -> None:
        for process in processes.values():
            if process.returncode is None:
                process.terminate()
                try:
                    async with async_timeout(5):
                        await process.wait()
                except TimeoutError:
                    process.kill()
                    await process.wait()