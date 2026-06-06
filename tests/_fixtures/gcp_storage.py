"""Shared fixtures for tests that need a local fake-gcs-server emulator.

Activate by adding `pytest_plugins = ["tests._fixtures.gcp_storage"]` at the top
of the consuming test module (or in a conftest.py).

The fixture launches a `fsouza/fake-gcs-server` container via `docker run`,
waits for the service to come up, and tears it down at module scope. Tests
are skipped when Docker or `gcloud-aio-storage` is unavailable.
"""

from __future__ import annotations

import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
import uuid

import pytest

pytest.importorskip("gcloud.aio.storage")

if shutil.which("docker") is None:
    pytest.skip("docker CLI not available", allow_module_level=True)


FAKE_GCS_IMAGE = "fsouza/fake-gcs-server:latest"


def _free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _wait_for_http(url: str, timeout: float = 30.0) -> None:
    """Poll an HTTP endpoint until it returns any response (even 4xx)."""
    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1.0)
            return
        except urllib.error.HTTPError:
            # any HTTP status means the server is up and routing requests
            return
        except (urllib.error.URLError, OSError) as e:
            last_error = e
            time.sleep(0.3)
    raise RuntimeError(f"fake-gcs-server at {url} did not become reachable in {timeout}s") from last_error


@pytest.fixture(scope="module")
def fake_gcs_endpoint():
    """Start a fake-gcs-server container for the duration of the test module."""
    port = _free_port()
    container_name = f"model-compose-test-fakegcs-{uuid.uuid4().hex[:8]}"
    public_host = f"127.0.0.1:{port}"

    try:
        subprocess.run(
            [
                "docker", "run", "-d", "--rm",
                "--name", container_name,
                "-p", f"{port}:4443",
                FAKE_GCS_IMAGE,
                "-scheme", "http",
                "-public-host", public_host,
                "-port", "4443",
            ],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as e:
        pytest.skip(f"failed to start fake-gcs-server container: {e.stderr.decode(errors='replace')}")

    try:
        endpoint = f"http://{public_host}"
        _wait_for_http(f"{endpoint}/storage/v1/b?project=test")
        yield endpoint
    finally:
        subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)
