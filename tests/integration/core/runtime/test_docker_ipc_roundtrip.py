"""End-to-end integration test: ComponentDockerRuntimeManager driving a
real docker container that hosts an `IpcRuntimeWorker` over the daemon's
attach stdin/stdout stream.

IPC travels over the docker daemon's attach socket, so there is no
bind-mounted unix socket — the test works uniformly on Linux native
daemons AND macOS Docker Desktop. Skipped only when the docker SDK
cannot reach a daemon at all.

Image strategy: we build a tiny ad-hoc image at module scope (slim
python + the host's `src/` bind-mounted at runtime). This avoids
shipping a real registry-tagged image and keeps the test isolated from
mindor's actual base image cache.
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import textwrap
from pathlib import Path
from typing import Any, Dict, Optional

import pytest


# ---------------------------------------------------------------------------
# Daemon detection.
# ---------------------------------------------------------------------------

def _docker_available() -> Optional[str]:
    try:
        import docker  # noqa: F401
    except ImportError as e:
        return f"docker SDK not installed: {e}"
    try:
        client = docker.from_env()
        client.ping()
    except Exception as e:
        return f"docker daemon not reachable: {e}"
    return None


_SKIP_REASON = _docker_available()
pytestmark = pytest.mark.skipif(_SKIP_REASON is not None, reason=_SKIP_REASON or "")


# ---------------------------------------------------------------------------
# Test image.
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[4]
SRC_DIR = REPO_ROOT / "src"


@pytest.fixture(scope="module")
def docker_image_tag() -> str:
    """Build a minimal image (python-slim + mindor's full runtime deps).

    The deps list is taken straight from `src/mindor/core/runtime/bootstrap/requirements.txt`
    — the same file production uses for the real base image — so the test
    image and prod image stay in lockstep without manual sync.

    We don't COPY the source in — the per-test container bind-mounts
    `src/` from the host so the test sees uncommitted changes immediately.
    """
    import docker
    client = docker.from_env()
    tag = "mindor-ipc-test:latest"

    # Build is keyed on a hash of the requirements file so we rebuild only
    # when the dep list actually changes.
    requirements_path = REPO_ROOT / "src" / "mindor" / "core" / "runtime" / "bootstrap" / "requirements.txt"
    requirements_bytes = requirements_path.read_bytes()

    try:
        existing = client.images.get(tag)
        stored_hash = (existing.labels or {}).get("mindor.test-requirements-sha256")
        current_hash = _sha256(requirements_bytes)
        if stored_hash == current_hash:
            return tag
        # Otherwise fall through and rebuild.
    except Exception:
        current_hash = _sha256(requirements_bytes)

    dockerfile = (
        "FROM python:3.11-slim\n"
        "COPY base-requirements.txt /tmp/base-requirements.txt\n"
        "RUN pip install --no-cache-dir -r /tmp/base-requirements.txt \\\n"
        "    && rm /tmp/base-requirements.txt\n"
        "WORKDIR /app\n"
        "ENV PYTHONPATH=/app/src\n"
    ).encode()

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        df_info = tarfile.TarInfo("Dockerfile")
        df_info.size = len(dockerfile)
        tar.addfile(df_info, io.BytesIO(dockerfile))
        req_info = tarfile.TarInfo("base-requirements.txt")
        req_info.size = len(requirements_bytes)
        tar.addfile(req_info, io.BytesIO(requirements_bytes))
    buf.seek(0)

    try:
        for _ in client.api.build(
            fileobj=buf,
            custom_context=True,
            tag=tag,
            rm=True,
            decode=True,
            labels={"mindor.test-requirements-sha256": current_hash},
        ):
            pass
    except Exception as e:
        pytest.skip(f"could not build test image: {e}")

    return tag


def _sha256(data: bytes) -> str:
    import hashlib
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# Echo worker script — written to a tempdir and bind-mounted at /app/worker.
# ---------------------------------------------------------------------------

ECHO_WORKER_SRC = textwrap.dedent("""
    from __future__ import annotations
    import asyncio, os, sys
    from mindor.core.component.runtime.base.ipc_stdio_channel import IpcStdioChannel
    from mindor.core.component.runtime.base.ipc_message import IpcMessage, IpcMessageType
    from mindor.core.component.runtime.base.ipc_worker import IpcRuntimeWorker
    from mindor.core.foundation.streaming.bytes import BytesStreamResource


    class EchoWorker(IpcRuntimeWorker):
        def __init__(self, worker_id, ipc_in, ipc_out):
            super().__init__(worker_id)
            self._ipc_in = ipc_in
            self._ipc_out = ipc_out
        async def _start(self): pass
        async def _stop(self): pass
        async def _execute_task(self, payload):
            cmd = payload["input"].get("cmd")
            if cmd == "echo":
                return {"echoed": payload["input"]["data"]}
            if cmd == "produce":
                size = payload["input"]["size"]
                chunk_size = payload["input"].get("chunk_size", 32)
                data = bytes((i & 0xFF) for i in range(size))
                return {"stream": BytesStreamResource(data, chunk_size=chunk_size)}
            if cmd == "produce_many":
                # Emit N distinct streams so the parent must demultiplex them.
                count = payload["input"]["count"]
                size = payload["input"]["size"]
                chunk_size = payload["input"].get("chunk_size", 32)
                streams = {}
                for i in range(count):
                    base = i * 0x10
                    data = bytes(((base + j) & 0xFF) for j in range(size))
                    streams[f"s{i}"] = BytesStreamResource(data, chunk_size=chunk_size)
                return streams
            if cmd == "produce_abort":
                # Yield one good chunk, then raise mid-stream so the container
                # emits STREAM_ABORT over the attach socket.
                from mindor.core.foundation.streaming.resources import StreamResource
                class _AbortingStream(StreamResource):
                    def __init__(self):
                        super().__init__(None, None, size=None)
                    async def close(self):
                        pass
                    async def _iterate_stream(self):
                        yield b"first-chunk-ok"
                        raise RuntimeError("intentional abort from worker")
                return {"stream": _AbortingStream()}
            if cmd == "consume":
                # Read the caller-provided stream and return what we saw.
                stream = payload["input"]["stream"]
                received = bytearray()
                async for chunk in stream:
                    received.extend(chunk)
                return {"received": bytes(received), "length": len(received)}
            return {"unknown": cmd}
        async def _send_message(self, message):
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._write_line, message)
        async def _recv_message(self):
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._read_line)
        def _write_line(self, message):
            self._ipc_out.write(message + b"\\n")
            self._ipc_out.flush()
        def _read_line(self):
            line = self._ipc_in.readline()
            if not line:
                return None
            return line.rstrip(b"\\n")
        def _close_transport(self):
            try: self._ipc_in.close()
            except Exception: pass
            try: self._ipc_out.close()
            except Exception: pass


    def main():
        channel = IpcStdioChannel()
        channel.setup()
        ipc_in, ipc_out = channel.ipc_in, channel.ipc_out
        init_line = ipc_in.readline()
        if not init_line:
            raise RuntimeError("expected START, got EOF")
        init = IpcMessage.deserialize(init_line.rstrip(b"\\n"))
        if init.type != IpcMessageType.START:
            raise RuntimeError(f"expected START, got {init.type}")
        worker_id = (init.payload or {}).get("component_id", "echo")
        worker = EchoWorker(worker_id, ipc_in, ipc_out)
        asyncio.run(worker.run())


    if __name__ == "__main__":
        main()
""")


@pytest.fixture
def echo_worker_dir():
    d = tempfile.mkdtemp(prefix="ew")
    (Path(d) / "echo_worker.py").write_text(ECHO_WORKER_SRC)
    yield d
    shutil.rmtree(d, ignore_errors=True)


# ---------------------------------------------------------------------------
# Minimal manager that mirrors ComponentDockerRuntimeManager but is wired
# directly to the echo worker (no embedded component bootstrapping).
# ---------------------------------------------------------------------------

class _AttachEchoManager:
    """Test scaffold equivalent to ComponentDockerRuntimeManager but minimal."""

    def __init__(self, image: str, worker_src_dir: str):
        from mindor.core.component.runtime.base.ipc_proxy import IpcRuntimeProxy
        from mindor.core.runtime.docker import DockerRuntime, DockerRuntimeParams
        from mindor.core.utils.channels.docker_attach import DockerAttachChannel
        from mindor.dsl.schema.runtime import DockerRuntimeConfig
        from mindor.dsl.schema.containers.docker import DockerVolumeConfig
        from mindor.dsl.schema.runtime.impl.common import RuntimeType

        import asyncio, ulid

        class _Manager(IpcRuntimeProxy):
            async def _start(self_inner): ...
            async def _stop(self_inner): ...
            async def _send_message(self_inner, message):
                await self_inner._loop.run_in_executor(None, self_inner._channel.send, message)
            async def _recv_message(self_inner):
                return await self_inner._loop.run_in_executor(None, self_inner._channel.recv)

        worker_id = f"echo-{ulid.ulid()}"

        runtime_config = DockerRuntimeConfig(
            type=RuntimeType.DOCKER,
            image=image,
            container_name=worker_id,
            volumes=[
                DockerVolumeConfig(type="bind", source=str(SRC_DIR), target="/app/src", read_only=True),
                DockerVolumeConfig(type="bind", source=worker_src_dir, target="/app/worker", read_only=True),
            ],
            environment={"PYTHONPATH": "/app/src:/app/worker"},
            entrypoint=["python", "-u", "/app/worker/echo_worker.py"],
        )

        self.manager = _Manager(worker_id)
        self.manager._start_timeout = 30.0
        self.manager._stop_timeout = 10.0
        self.manager._runtime = DockerRuntime(
            DockerRuntimeParams.from_config(runtime_config), verbose=False,
        )
        self._DockerAttachChannel = DockerAttachChannel

    async def start(self):
        import asyncio
        from mindor.core.component.runtime.base.ipc_message import IpcMessage, IpcMessageType
        m = self.manager
        m._loop = asyncio.get_event_loop()

        if await m._runtime.exists():
            await m._runtime.remove(force=True)
        # Attach mode requires tty=False so the daemon emits stdout/stderr as
        # distinct multiplex frames.
        await m._runtime.create(tty=False, stdin_open=True)

        # Attach BEFORE start, so we don't miss the worker's first byte.
        m._channel = await m._loop.run_in_executor(None, self._attach_to_container)
        await m._runtime.start(detach=True)

        await m._send_message(IpcMessage(
            type=IpcMessageType.START,
            payload={"component_id": m.worker_id},
        ).serialize())
        try:
            await m._wait_for_ready()
        except Exception as e:
            container_logs = await self._collect_container_logs()
            raise RuntimeError(
                f"{e}\n---- container logs ----\n{container_logs}\n----"
            ) from e
        m._response_task = asyncio.create_task(m._handle_responses())

    async def _collect_container_logs(self) -> str:
        import docker
        try:
            client = docker.from_env()
            container = client.containers.get(self.manager.worker_id)
            return container.logs(stdout=True, stderr=True).decode("utf-8", errors="replace")
        except Exception as e:
            return f"<failed to fetch logs: {e}>"

    def _attach_to_container(self):
        import docker
        client = docker.from_env()
        container = client.containers.get(self.manager.worker_id)
        sock = container.attach_socket(params={
            "stdin": 1, "stdout": 1, "stderr": 1, "stream": 1,
        })
        return self._DockerAttachChannel(sock)

    async def stop(self):
        import asyncio
        m = self.manager
        try:
            await m._send_stop_message()
        except Exception:
            pass
        try:
            await m._runtime.stop()
            await m._runtime.remove(force=True)
        except Exception:
            pass
        if m._response_task is not None:
            try:
                await asyncio.wait_for(m._response_task, timeout=m._stop_timeout)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                m._response_task.cancel()
        if getattr(m, "_channel", None) is not None:
            m._channel.close()

    async def execute(self, payload):
        return await self.manager.request(payload)


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_inline_echo_roundtrip(docker_image_tag, echo_worker_dir):
    """Tier B: bytes payload survives the docker attach transport."""
    mgr = _AttachEchoManager(docker_image_tag, echo_worker_dir)
    await mgr.start()
    try:
        result = await mgr.execute({
            "action_id": "noop",
            "run_id": "r1",
            "input": {"cmd": "echo", "data": b"hello docker\x00\xff"},
        })
        assert result == {"echoed": b"hello docker\x00\xff"}
    finally:
        await mgr.stop()


@pytest.mark.anyio
async def test_stream_output_roundtrip(docker_image_tag, echo_worker_dir):
    """Tier C output: container-side BytesStreamResource flows out via
    STREAM_PULL/CHUNK/END over the attach stdout stream."""
    from mindor.core.foundation.streaming.resources import StreamResource

    mgr = _AttachEchoManager(docker_image_tag, echo_worker_dir)
    await mgr.start()
    try:
        result = await mgr.execute({
            "action_id": "noop",
            "run_id": "r1",
            "input": {"cmd": "produce", "size": 256, "chunk_size": 32},
        })

        stream = result["stream"]
        assert isinstance(stream, StreamResource)
        received = bytearray()
        async for chunk in stream:
            received.extend(chunk)

        assert bytes(received) == bytes((i & 0xFF) for i in range(256))
    finally:
        await mgr.stop()


@pytest.mark.anyio
async def test_large_payload_survives_attach_framing(docker_image_tag, echo_worker_dir):
    """A single IPC message larger than a typical attach multiplex frame must
    reassemble correctly on the parent side. Exercises the readline-based
    framing over the attach socket's stdout stream."""
    mgr = _AttachEchoManager(docker_image_tag, echo_worker_dir)
    await mgr.start()
    try:
        large = bytes((i & 0xFF) for i in range(64 * 1024))
        result = await mgr.execute({
            "action_id": "noop",
            "run_id": "r1",
            "input": {"cmd": "echo", "data": large},
        })
        assert result == {"echoed": large}
    finally:
        await mgr.stop()


@pytest.mark.anyio
async def test_inbound_stream_roundtrip(docker_image_tag, echo_worker_dir):
    """Tier C input: parent-side BytesStreamResource flows into the container
    via STREAM_PULL/CHUNK/END on the attach stdin stream."""
    from mindor.core.foundation.streaming.bytes import BytesStreamResource

    mgr = _AttachEchoManager(docker_image_tag, echo_worker_dir)
    await mgr.start()
    try:
        payload = bytes((i & 0xFF) for i in range(1024))
        result = await mgr.execute({
            "action_id": "noop",
            "run_id": "r1",
            "input": {
                "cmd": "consume",
                "stream": BytesStreamResource(payload, chunk_size=64),
            },
        })
        assert result == {"received": payload, "length": len(payload)}
    finally:
        await mgr.stop()


@pytest.mark.anyio
async def test_multiple_streams_demultiplex(docker_image_tag, echo_worker_dir):
    """Multiple distinct streams in one RESULT must not have their chunks
    interleaved on the parent side — each stream_id is demultiplexed
    independently."""
    from mindor.core.foundation.streaming.resources import StreamResource

    mgr = _AttachEchoManager(docker_image_tag, echo_worker_dir)
    await mgr.start()
    try:
        result = await mgr.execute({
            "action_id": "noop",
            "run_id": "r1",
            "input": {"cmd": "produce_many", "count": 3, "size": 128, "chunk_size": 16},
        })

        for i in range(3):
            stream = result[f"s{i}"]
            assert isinstance(stream, StreamResource)
            received = bytearray()
            async for chunk in stream:
                received.extend(chunk)
            base = i * 0x10
            assert bytes(received) == bytes(((base + j) & 0xFF) for j in range(128))
    finally:
        await mgr.stop()


@pytest.mark.anyio
async def test_stream_abort_propagates(docker_image_tag, echo_worker_dir):
    """When the container-side stream raises mid-iteration, STREAM_ABORT must
    reach the parent and surface as an exception on the consumer."""
    from mindor.core.foundation.streaming.resources import StreamResource

    mgr = _AttachEchoManager(docker_image_tag, echo_worker_dir)
    await mgr.start()
    try:
        result = await mgr.execute({
            "action_id": "noop",
            "run_id": "r1",
            "input": {"cmd": "produce_abort"},
        })
        stream = result["stream"]
        assert isinstance(stream, StreamResource)

        received_first = False
        with pytest.raises(Exception):
            async for chunk in stream:
                if not received_first:
                    assert chunk == b"first-chunk-ok"
                    received_first = True
        assert received_first, "first chunk should arrive before the abort"
    finally:
        await mgr.stop()


@pytest.mark.anyio
async def test_container_kill_releases_pending_run(docker_image_tag, echo_worker_dir):
    """`docker kill` while NO RUN is in flight, followed by a fresh execute(),
    must trip `_abort_pending_on_eof` so the caller wakes up with
    ConnectionError instead of hanging forever on a dead transport.

    We kill *first* (deterministic), then issue the RUN. The send path may
    succeed (kernel still buffers stdin), but the response will never come
    because the worker is gone — `_handle_responses` hits EOF and aborts
    every pending future.
    """
    import asyncio
    import docker

    mgr = _AttachEchoManager(docker_image_tag, echo_worker_dir)
    await mgr.start()
    try:
        client = docker.from_env()
        container = client.containers.get(mgr.manager.worker_id)

        container.kill()

        # The response task should observe EOF imminently. Issue a RUN and
        # confirm we get woken up rather than parked forever.
        with pytest.raises(ConnectionError):
            await asyncio.wait_for(
                mgr.execute({
                    "action_id": "noop",
                    "run_id": "r-kill",
                    "input": {"cmd": "echo", "data": b"after kill"},
                }),
                timeout=10.0,
            )
    finally:
        try:
            await mgr.stop()
        except Exception:
            pass
