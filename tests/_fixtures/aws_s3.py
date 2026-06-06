"""Shared fixtures for tests that need an in-process moto S3 server.

Activate by adding `pytest_plugins = ["tests._fixtures.aws_s3"]` at the top
of the consuming test module (or in a conftest.py).
"""

from __future__ import annotations

import pytest

pytest.importorskip("moto")
pytest.importorskip("aioboto3")

import aioboto3
from moto.server import ThreadedMotoServer


DEFAULT_REGION = "us-east-1"


@pytest.fixture(autouse=True)
def aws_credentials(monkeypatch):
    """Mocked AWS credentials so botocore does not pick up real ones."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", DEFAULT_REGION)


@pytest.fixture(scope="module")
def moto_endpoint():
    """Run an in-process moto S3 server so aiobotocore makes real HTTP calls into it."""
    server = ThreadedMotoServer(port=0)
    server.start()
    host, port = server.get_host_and_port()
    yield f"http://{host}:{port}"
    server.stop()


@pytest.fixture
async def s3_session(moto_endpoint):
    """An aioboto3 Session pointing at the moto endpoint."""
    yield aioboto3.Session()


@pytest.fixture
async def s3_client_factory(moto_endpoint, s3_session):
    """Return an async context manager factory that yields an S3 client.

    Usage:
        async with s3_client_factory() as client:
            await client.create_bucket(Bucket="x")
    """
    def _factory():
        return s3_session.client("s3", region_name=DEFAULT_REGION, endpoint_url=moto_endpoint)

    return _factory
