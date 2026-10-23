"""A reader that stops a streamed http output early ends the HTTP request behind it.

When a consumer stops reading (a WebSocket client sends `stream_close` or
disconnects, an HTTP client goes away), the response must be closed; otherwise
the server keeps producing, e.g. an LLM keeps generating tokens nobody will read.
"""

import asyncio

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer
from unittest.mock import AsyncMock, MagicMock

from mindor.core.component.services.http_client import HttpClientAction
from mindor.core.component.services.http_server import HttpServerAction
from mindor.core.component.streaming import ComponentOutputStreamIterator
from mindor.core.controller.adapters.services.websocket_stream import WebSocketOutboundStream
from mindor.core.controller.streaming import TaskOutputStreamEncodingIterator
from mindor.core.foundation.streaming.iterators import StreamEncodingIterator
from mindor.core.foundation.variable.codec import StreamKind, VariableCodec
from mindor.core.utils.transport.http_client import HttpClient
from mindor.core.workflow.job.streaming import JobOutputStreamIterator
from mindor.dsl.schema.action.impl.http_client import HttpClientActionConfig
from mindor.dsl.schema.action.impl.http_server import HttpServerActionConfig


@pytest.fixture
def anyio_backend():
    return "asyncio"


class SlowEventServer:
    """Sends one server-sent event every 20 ms, up to 500, and notes when the client goes away."""

    def __init__(self) -> None:
        self.disconnected = asyncio.Event()
        self.sent = 0

    async def handle(self, request: web.Request) -> web.StreamResponse:
        response = web.StreamResponse(headers={"Content-Type": "text/event-stream"})
        await response.prepare(request)
        try:
            for i in range(500):
                await response.write(f"data: {i}\n\n".encode())
                self.sent += 1
                await asyncio.sleep(0.02)
        except (ConnectionResetError, asyncio.CancelledError):
            self.disconnected.set()
            raise
        return response


@pytest.fixture
async def served():
    events = SlowEventServer()
    app = web.Application()
    app.router.add_post("/events", events.handle)
    server = TestServer(app)
    await server.start_server()
    client = HttpClient(base_url=str(server.make_url("/")))
    yield client, events
    await client.close()
    await server.close()


async def _stream(client, action=None):
    context = MagicMock()
    context.render_variable = AsyncMock(side_effect=lambda value, **_: value)
    action = action or HttpClientAction(HttpClientActionConfig(path="/events", method="POST"))
    return await action.run(context, client)


def _wrapped(stream):
    # The layers a workflow puts between a component's stream and the task output.
    component = ComponentOutputStreamIterator(stream, AsyncMock())
    job = JobOutputStreamIterator(component, AsyncMock())
    return TaskOutputStreamEncodingIterator(StreamEncodingIterator(job), AsyncMock())


@pytest.mark.anyio
@pytest.mark.parametrize("action", [
    HttpClientAction(HttpClientActionConfig(path="/events", method="POST")),
    HttpServerAction(HttpServerActionConfig(path="/events", method="POST")),
], ids=["http-client", "http-server"])
async def test_closing_the_stream_ends_the_request(served, action):
    client, events = served
    iterator = (await _stream(client, action)).__aiter__()

    assert [await iterator.__anext__() for _ in range(2)] == [b"0", b"1"]
    await iterator.aclose()

    await asyncio.wait_for(events.disconnected.wait(), 1.0)
    assert events.sent < 100


@pytest.mark.anyio
async def test_closing_an_outbound_websocket_stream_ends_the_request(served):
    # The WebSocket server holds a workflow's streamed output and closes it on `stream_close`.
    client, events = served
    outbound = WebSocketOutboundStream("s1", StreamKind.BYTES, _wrapped(await _stream(client)), VariableCodec())

    assert await outbound.next_chunk() == b"0"
    await outbound.aclose()

    await asyncio.wait_for(events.disconnected.wait(), 1.0)


@pytest.mark.anyio
async def test_a_consumer_that_never_read_does_not_end_the_stream(served):
    # One output, two holders (say two subscribers of the task): the one that never
    # pulled lets go, the one reading keeps its stream.
    client, events = served
    output = _wrapped(await _stream(client))
    reader = WebSocketOutboundStream("s1", StreamKind.BYTES, output, VariableCodec())
    idle = WebSocketOutboundStream("s2", StreamKind.BYTES, output, VariableCodec())

    assert await reader.next_chunk() == b"0"
    await idle.aclose()
    assert [await reader.next_chunk() for _ in range(3)] == [b"1", b"2", b"3"]
    assert not events.disconnected.is_set()

    await reader.aclose()
    await asyncio.wait_for(events.disconnected.wait(), 1.0)
