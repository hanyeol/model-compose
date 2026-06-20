"""Fixtures for file_store integration tests.

Provides Azurite (Azure blob) and fake-gcs-server (GCS) emulators launched via
`docker run`, plus reuses the moto S3 fixtures defined in
tests/integration/conftest.py.

Each fixture skips on demand if its prerequisite SDK or `docker` is unavailable,
so unrelated file_store tests (e.g. local backend) still run.
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


# Well-known Azurite account — accepted by every Azure SDK and documented by Microsoft.
AZURITE_ACCOUNT = "devstoreaccount1"
AZURITE_KEY = (
    "Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw=="
)
AZURITE_IMAGE = "mcr.microsoft.com/azure-storage/azurite:latest"
FAKE_GCS_IMAGE = "fsouza/fake-gcs-server:latest"


def _free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _wait_for_http(url: str, what: str, timeout: float = 30.0) -> None:
    """Poll an HTTP endpoint until it returns any response (even 4xx)."""
    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1.0)
            return
        except urllib.error.HTTPError:
            return
        except (urllib.error.URLError, OSError) as e:
            last_error = e
            time.sleep(0.3)
    raise RuntimeError(f"{what} at {url} did not become reachable in {timeout}s") from last_error


def _require_docker() -> None:
    if shutil.which("docker") is None:
        pytest.skip("docker CLI not available")


@pytest.fixture(scope="module")
def azurite_endpoint():
    """Start an Azurite container for the duration of the test module."""
    pytest.importorskip("azure.storage.blob")
    pytest.importorskip("azure.storage.blob.aio")
    _require_docker()

    port = _free_port()
    container_name = f"model-compose-test-azurite-{uuid.uuid4().hex[:8]}"

    try:
        subprocess.run(
            [
                "docker", "run", "-d", "--rm",
                "--name", container_name,
                "-p", f"{port}:10000",
                AZURITE_IMAGE,
                "azurite-blob",
                "--blobHost", "0.0.0.0",
                "--blobPort", "10000",
                "--skipApiVersionCheck",
            ],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as e:
        pytest.skip(f"failed to start Azurite container: {e.stderr.decode(errors='replace')}")

    try:
        endpoint = f"http://127.0.0.1:{port}/{AZURITE_ACCOUNT}"
        _wait_for_http(endpoint, "Azurite")
        yield endpoint
    finally:
        subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)


@pytest.fixture
def azurite_connection_string(azurite_endpoint):
    """Connection string pointing at the running Azurite blob endpoint."""
    return (
        f"DefaultEndpointsProtocol=http;"
        f"AccountName={AZURITE_ACCOUNT};"
        f"AccountKey={AZURITE_KEY};"
        f"BlobEndpoint={azurite_endpoint};"
    )


@pytest.fixture(scope="module")
def fake_gcs_endpoint():
    """Start a fake-gcs-server container for the duration of the test module."""
    pytest.importorskip("gcloud.aio.storage")
    _require_docker()

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
        _wait_for_http(f"{endpoint}/storage/v1/b?project=test", "fake-gcs-server")
        yield endpoint
    finally:
        subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)
