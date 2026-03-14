from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Iterator, Any
from mindor.dsl.schema.gateway import CloudflareHttpTunnelGatewayConfig
from ..base import CommonHttpTunnelGateway
from mindor.core.logger import logging
import asyncio
import re
import tempfile
import os

if TYPE_CHECKING:
    pass

class CloudflareHttpTunnelGateway(CommonHttpTunnelGateway):
    QUICK_TUNNEL_URL_PATTERN = re.compile(r"https://[a-zA-Z0-9\-]+\.trycloudflare\.com")
    TUNNEL_READY_TIMEOUT = 30

    def __init__(self, config: CloudflareHttpTunnelGatewayConfig):
        super().__init__(config)

        self.processes: Optional[Dict[int, asyncio.subprocess.Process]] = None
        self._tmp_config_path: Optional[str] = None

    async def _serve(self) -> Optional[Dict[int, str]]:
        self.processes = {}

        if self._is_named_tunnel():
            return await self._serve_named_tunnel()
        else:
            return await self._serve_quick_tunnel()

    async def _shutdown(self) -> None:
        seen = set()
        for process in self.processes.values():
            if id(process) in seen:
                continue
            seen.add(id(process))

            if process.returncode is None:
                process.terminate()
                try:
                    async with asyncio.timeout(5):
                        await process.wait()
                except TimeoutError:
                    process.kill()
                    await process.wait()

        self.processes = None

        if self._tmp_config_path:
            try:
                os.unlink(self._tmp_config_path)
            except OSError:
                pass
            self._tmp_config_path = None

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

    async def _serve_named_tunnel(self) -> Dict[int, str]:
        cmd = self._build_named_tunnel_command()

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        await self._wait_for_named_tunnel_ready(process)

        for port in self.config.port:
            self.processes[port] = process

        return self._resolve_named_tunnel_urls()

    def _build_named_tunnel_command(self) -> List[str]:
        if self.config.token:
            return [ "cloudflared", "tunnel", "run", "--token", self.config.token ]

        config_content = self._build_config_yaml(self.config.tunnel, self.config.credentials_file)

        fd, path = tempfile.mkstemp(suffix=".yml", prefix="cloudflared-")
        with os.fdopen(fd, "w") as f:
            f.write(config_content)
        self._tmp_config_path = path

        return [ "cloudflared", "tunnel", "--config", path, "run", self.config.tunnel ]

    def _build_config_yaml(self, tunnel: str, credentials_file: str) -> str:
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

        return {port: base_url for port in self.config.port}

    def _is_named_tunnel(self) -> bool:
        return bool(self.config.token or self.config.tunnel)

    async def _wait_for_quick_tunnel_url(self, process: asyncio.subprocess.Process) -> Optional[str]:
        try:
            async with asyncio.timeout(self.TUNNEL_READY_TIMEOUT):
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

    async def _wait_for_named_tunnel_ready(self, process: asyncio.subprocess.Process) -> None:
        try:
            async with asyncio.timeout(self.TUNNEL_READY_TIMEOUT):
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
