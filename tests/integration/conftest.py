"""Fixtures shared across the integration tier.

Provides an in-process moto S3 server and the supporting `s3_*` fixtures.
Subdirectory conftests can extend this (see file_store/conftest.py for the
Azurite blob and fake-gcs emulators).
"""

from __future__ import annotations

import pytest

DEFAULT_AWS_REGION = "us-east-1"


@pytest.fixture
def aws_credentials(monkeypatch):
    """Stub AWS credentials so botocore does not pick up real ones."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", DEFAULT_AWS_REGION)


@pytest.fixture(scope="module")
def moto_endpoint():
    """Run an in-process moto S3 server so aiobotocore makes real HTTP calls into it."""
    pytest.importorskip("moto")
    from moto.server import ThreadedMotoServer

    server = ThreadedMotoServer(port=0)
    server.start()
    host, port = server.get_host_and_port()
    try:
        yield f"http://{host}:{port}"
    finally:
        server.stop()


@pytest.fixture
async def s3_session(aws_credentials, moto_endpoint):
    """An aioboto3 Session pointing at the moto endpoint."""
    aioboto3 = pytest.importorskip("aioboto3")
    yield aioboto3.Session()


@pytest.fixture
async def s3_client_factory(moto_endpoint, s3_session):
    """Return a factory that yields an aioboto3 S3 client context manager.

    Usage:
        async with s3_client_factory() as client:
            await client.create_bucket(Bucket="x")
    """
    def _factory():
        return s3_session.client("s3", region_name=DEFAULT_AWS_REGION, endpoint_url=moto_endpoint)

    return _factory
