"""E2E test: graceful shutdown behavior of the HTTP controller.

Boots a minimal ControllerService with an `http-server` adapter, then exercises
the two-phase shutdown:

1. Normal state: `/health` returns 200.
2. `shutdown_pending` phase (grace period): `/health` returns 503 with
   `status: shutdown_pending`, but workflow requests are still accepted.
3. `shutting_down` phase: `/health` returns 503 with `status: shutting_down`
   and workflow requests are rejected with 503.
4. In-flight requests started before shutdown complete successfully.
"""

from __future__ import annotations

import asyncio
import socket
from contextlib import closing
from typing import Optional, Tuple

import aiohttp
import pytest

from mindor.core.component.component import ComponentInstances
from mindor.core.controller.adapters.adapter import AdapterInstances
from mindor.core.controller.base import ControllerService
from mindor.core.controller.controller import create_controller
from mindor.dsl.schema.compose import ComposeConfig


@pytest.fixture(autouse=True)
def reset_singletons():
    ComponentInstances.clear()
    AdapterInstances.clear()
    ControllerService._shared_instance = None
    yield
    ComponentInstances.clear()
    AdapterInstances.clear()
    ControllerService._shared_instance = None


def _free_port() -> int:
    """Grab a free port. SO_REUSEADDR avoids TIME_WAIT collisions from
    uvicorn instances that a previous test left behind."""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _build_compose(port: int, pending_period: str = "0s", sleep_seconds: float = 0) -> ComposeConfig:
    return ComposeConfig.model_validate({
        "controller": {
            "name": "test-shutdown",
            "runtime": "native",
            "max_concurrent_count": 0,
            "shutdown_pending_period": pending_period,
            "shutdown_timeout": "5s",
            "adapters": [
                {
                    "type": "http-server",
                    "host": "127.0.0.1",
                    "port": port,
                    "base_path": "/api",
                }
            ],
        },
        "components": [
            {
                "id": "slow-echo",
                "type": "shell",
                "action": {
                    "command": [
                        "python3", "-c",
                        f"import sys, time; time.sleep({sleep_seconds}); print(sys.argv[1])",
                        "${input.message}",
                    ],
                    "output": "${result.stdout}",
                },
            },
        ],
        "workflows": [
            {
                "id": "echo",
                "title": "Echo",
                "description": "Echo the input message.",
                "job": {
                    "component": "slow-echo",
                    "input": { "message": "${input.message}" },
                    "output": "${output}",
                },
            }
        ],
    })


async def _wait_for_port(host: str, port: int, timeout: float = 5.0) -> None:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        try:
            reader, writer = await asyncio.open_connection(host, port)
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            return
        except (ConnectionRefusedError, OSError):
            await asyncio.sleep(0.05)
    raise TimeoutError(f"HTTP server did not start on {host}:{port} within {timeout}s")


async def _get_health(base_url: str) -> Tuple[int, Optional[dict]]:
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{base_url}/health") as resp:
                return resp.status, await resp.json()
        except (aiohttp.ClientConnectorError, aiohttp.ServerDisconnectedError):
            return -1, None


async def _post_workflow(base_url: str, message: str, timeout: float = 10.0) -> Tuple[int, Optional[dict]]:
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                f"{base_url}/workflows/runs",
                json={
                    "workflow_id": "echo",
                    "input": { "message": message },
                    "wait_for_completion": True,
                },
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                if resp.status == 200:
                    return resp.status, await resp.json()
                return resp.status, None
        except (aiohttp.ClientConnectorError, aiohttp.ServerDisconnectedError):
            return -1, None


async def _make_controller(port: int, pending_period: str = "0s", sleep_seconds: float = 0):
    compose = _build_compose(port, pending_period, sleep_seconds)
    controller = create_controller(
        compose.controller,
        compose.workflows,
        compose.components,
        compose.systems,
        compose.listeners,
        compose.gateways,
        compose.tracers,
        compose.loggers,
        daemon=True,
    )
    await controller.start()
    await _wait_for_port("127.0.0.1", port)
    return controller


async def _fully_stop(controller) -> None:
    """Stop the controller and wait until the daemon serve loop actually exits,
    so the underlying TCP port is fully released before the next test binds."""
    await controller.stop()
    await controller.wait_until_stopped()


class TestGracefulShutdown:
    def test_healthcheck_ok_when_running(self):
        async def scenario():
            port = _free_port()
            controller = await _make_controller(port)
            try:
                status, body = await _get_health(f"http://127.0.0.1:{port}/api")
                assert status == 200
                assert body == { "status": "ok" }
            finally:
                await _fully_stop(controller)

        asyncio.run(scenario())

    def test_shutdown_pending_returns_503_but_accepts_requests(self):
        """During shutdown_pending, /health is 503 but workflows still run."""
        async def scenario():
            port = _free_port()
            base_url = f"http://127.0.0.1:{port}/api"
            controller = await _make_controller(port, pending_period="2s")

            # Kick off shutdown in the background so we can observe the pending phase.
            stop_task = asyncio.create_task(controller.stop())

            # Give the controller a moment to enter shutdown_pending.
            await asyncio.sleep(0.2)

            try:
                status, body = await _get_health(base_url)
                assert status == 503, f"expected 503 during pending, got {status}"
                assert body == { "status": "shutdown_pending" }

                # A workflow request should still succeed during the pending phase.
                status, body = await _post_workflow(base_url, "hello-pending")
                assert status == 200, f"expected 200 for workflow during pending, got {status}"
                assert body is not None
                assert "hello-pending" in body.get("output", "")
            finally:
                await stop_task
                await controller.wait_until_stopped()

        asyncio.run(scenario())

    def test_shutting_down_rejects_new_requests(self):
        """After the pending period elapses, workflow requests are rejected."""
        async def scenario():
            port = _free_port()
            base_url = f"http://127.0.0.1:{port}/api"
            # No pending phase — go straight to shutting_down. A long in-flight
            # workflow keeps the HTTP server alive during the drain window so
            # we can observe the shutting_down state.
            controller = await _make_controller(port, pending_period="0s", sleep_seconds=3)

            # Start a long-running in-flight workflow.
            inflight = asyncio.create_task(_post_workflow(base_url, "keep-alive", timeout=10.0))
            await asyncio.sleep(0.3)  # let it reach the shell handler

            stop_task = asyncio.create_task(controller.stop())
            # Yield so _stop() flips _shutting_down = True.
            await asyncio.sleep(0.1)

            try:
                status, body = await _get_health(base_url)
                assert status == 503, f"expected 503 shutting_down, got {status}"
                assert body == { "status": "shutting_down" }

                status, _ = await _post_workflow(base_url, "hello-shutdown", timeout=2.0)
                assert status == 503, f"expected 503 rejection, got {status}"
            finally:
                await inflight  # let the keep-alive request finish
                await stop_task
                await controller.wait_until_stopped()

        asyncio.run(scenario())

    def test_in_flight_request_completes_during_shutdown(self):
        """A workflow started before shutdown should finish successfully."""
        async def scenario():
            port = _free_port()
            base_url = f"http://127.0.0.1:{port}/api"
            controller = await _make_controller(port, pending_period="0s", sleep_seconds=1.5)

            # Start a long-running workflow.
            request_task = asyncio.create_task(_post_workflow(base_url, "slow", timeout=10.0))

            # Let the workflow reach the shell handler.
            await asyncio.sleep(0.3)

            # Now trigger shutdown; the in-flight request should still complete.
            stop_task = asyncio.create_task(controller.stop())

            status, body = await request_task
            assert status == 200, f"in-flight request should succeed, got {status}"
            assert body is not None
            assert "slow" in body.get("output", "")

            await stop_task
            await controller.wait_until_stopped()

        asyncio.run(scenario())
