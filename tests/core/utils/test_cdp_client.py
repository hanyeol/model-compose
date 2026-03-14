import pytest
import asyncio
import os
import platform
import shutil
import socket
import subprocess
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch, call
from mindor.core.utils.cdp_client import CdpClient

CDP_BASE_PORT = 9222

def _find_chrome() -> str | None:
    """Find the Chrome executable path for the current OS."""
    system = platform.system()
    if system == "Darwin":
        path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        if os.path.exists(path):
            return path
    elif system == "Linux":
        for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
            path = shutil.which(name)
            if path:
                return path
    elif system == "Windows":
        for base in (
            os.environ.get("PROGRAMFILES", r"C:\Program Files"),
            os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
            os.environ.get("LOCALAPPDATA", ""),
        ):
            path = os.path.join(base, "Google", "Chrome", "Application", "chrome.exe")
            if os.path.exists(path):
                return path
    return None

CHROME_PATH = _find_chrome()
CHROME_AVAILABLE = CHROME_PATH is not None

# ---- Fixtures ----

@pytest.fixture
def anyio_backend():
    return "asyncio"

@pytest.fixture
def mock_ws():
    """Create a mock WebSocketClient."""
    ws = MagicMock()
    ws.connect = AsyncMock()
    ws.close = AsyncMock()
    ws.send_message = AsyncMock()
    ws.receive_message = AsyncMock()
    return ws

@pytest.fixture
def client():
    """Create a CdpClient instance with short timeout for tests."""
    return CdpClient("ws://localhost:9222/devtools/page/test", timeout=1.0)

def _find_free_port(start: int = CDP_BASE_PORT, end: int = CDP_BASE_PORT + 100) -> int:
    """Find a free port starting from start."""
    for port in range(start, end):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("localhost", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No free port found in range {start}-{end}")

@pytest.fixture(scope="module")
def chrome():
    """Launch a headless Chrome instance for the entire test module."""
    if not CHROME_AVAILABLE:
        pytest.skip("Google Chrome not found")

    port = _find_free_port()
    user_data_dir = tempfile.mkdtemp(prefix="cdp-test-")

    proc = subprocess.Popen(
        [
            CHROME_PATH,
            "--headless",
            "--disable-gpu",
            f"--remote-debugging-port={port}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
            "--disable-background-networking",
            "--disable-sync",
            f"--user-data-dir={user_data_dir}",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    import aiohttp

    async def _wait_for_cdp():
        for _ in range(30):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"http://localhost:{port}/json") as resp:
                        if resp.status == 200:
                            return
            except (aiohttp.ClientError, OSError):
                pass
            await asyncio.sleep(0.3)
        raise RuntimeError("Chrome did not start in time")

    asyncio.run(_wait_for_cdp())

    yield {"proc": proc, "port": port}

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()

# ---- Unit Tests (mocked) ----

class TestCdpClientConnection:
    """Test connection lifecycle."""

    @pytest.mark.anyio
    async def test_connect(self, client, mock_ws):
        """Test that connect() creates WebSocketClient, connects, and starts reader task."""
        with patch("mindor.core.utils.cdp_client.WebSocketClient", return_value=mock_ws):
            await client.connect()

            mock_ws.connect.assert_awaited_once()
            assert client._ws is mock_ws
            assert client._reader_task is not None

            await client.close()

    @pytest.mark.anyio
    async def test_close(self, client, mock_ws):
        """Test that close() cancels reader task and closes WebSocket."""
        with patch("mindor.core.utils.cdp_client.WebSocketClient", return_value=mock_ws):
            mock_ws.receive_message.side_effect = asyncio.CancelledError
            await client.connect()

            await client.close()

            mock_ws.close.assert_awaited_once()
            assert client._reader_task is None
            assert client._ws is None

    @pytest.mark.anyio
    async def test_close_idempotent(self, client):
        """Test that close() is safe when not connected."""
        await client.close()

        assert client._reader_task is None
        assert client._ws is None


class TestCdpClientSendCommand:
    """Test CDP command sending and response handling."""

    @pytest.mark.anyio
    async def test_send_command_success(self, client, mock_ws):
        """Test sending a command and receiving a successful response."""
        with patch("mindor.core.utils.cdp_client.WebSocketClient", return_value=mock_ws):
            call_count = 0
            async def fake_receive():
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    while not client._pending:
                        await asyncio.sleep(0)
                    return {"id": 1, "result": {"frameId": "abc"}}
                raise asyncio.CancelledError

            mock_ws.receive_message = fake_receive

            await client.connect()
            result = await client.send_command("Page.navigate", {"url": "https://example.com"})

            assert result == {"frameId": "abc"}

            sent = mock_ws.send_message.call_args[0][0]
            assert sent["method"] == "Page.navigate"
            assert sent["params"] == {"url": "https://example.com"}
            assert sent["id"] == 1

            await client.close()

    @pytest.mark.anyio
    async def test_send_command_without_params(self, client, mock_ws):
        """Test sending a command without params defaults to empty dict."""
        with patch("mindor.core.utils.cdp_client.WebSocketClient", return_value=mock_ws):
            mock_ws.receive_message.side_effect = [
                {"id": 1, "result": {}},
                asyncio.CancelledError,
            ]
            await client.connect()
            await client.send_command("Page.enable")

            sent = mock_ws.send_message.call_args[0][0]
            assert sent["params"] == {}

            await client.close()

    @pytest.mark.anyio
    async def test_send_command_cdp_error(self, client, mock_ws):
        """Test that CDP error response raises RuntimeError."""
        with patch("mindor.core.utils.cdp_client.WebSocketClient", return_value=mock_ws):
            mock_ws.receive_message.side_effect = [
                {"id": 1, "error": {"code": -32000, "message": "Not found"}},
                asyncio.CancelledError,
            ]
            await client.connect()

            with pytest.raises(RuntimeError, match="CDP error"):
                await client.send_command("DOM.getDocument")

            await client.close()

    @pytest.mark.anyio
    async def test_send_command_timeout(self, client, mock_ws):
        """Test that TimeoutError is raised when no response arrives."""
        with patch("mindor.core.utils.cdp_client.WebSocketClient", return_value=mock_ws):
            async def hang_forever():
                await asyncio.sleep(100)

            mock_ws.receive_message.side_effect = hang_forever
            await client.connect()

            with pytest.raises(TimeoutError, match="timed out"):
                await client.send_command("Page.navigate")

            assert len(client._pending) == 0

            await client.close()

    @pytest.mark.anyio
    async def test_send_command_id_increment(self, client, mock_ws):
        """Test that command IDs increment sequentially."""
        with patch("mindor.core.utils.cdp_client.WebSocketClient", return_value=mock_ws):
            expected_id = 0
            async def fake_receive():
                nonlocal expected_id
                expected_id += 1
                if expected_id <= 3:
                    while expected_id not in client._pending:
                        await asyncio.sleep(0)
                    return {"id": expected_id, "result": {}}
                raise asyncio.CancelledError

            mock_ws.receive_message = fake_receive
            await client.connect()

            await client.send_command("Cmd.A")
            await client.send_command("Cmd.B")
            await client.send_command("Cmd.C")

            ids = [c[0][0]["id"] for c in mock_ws.send_message.call_args_list]
            assert ids == [1, 2, 3]

            await client.close()


class TestCdpClientEvents:
    """Test event listener registration and dispatch."""

    def test_on_event_registers_callback(self, client):
        """Test that on_event registers a callback."""
        callback = AsyncMock()
        client.on_event("Page.loadEventFired", callback)

        assert callback in client._event_listeners["Page.loadEventFired"]

    def test_multiple_event_listeners(self, client):
        """Test registering multiple listeners for the same event."""
        cb1 = AsyncMock()
        cb2 = AsyncMock()
        client.on_event("Page.loadEventFired", cb1)
        client.on_event("Page.loadEventFired", cb2)

        assert len(client._event_listeners["Page.loadEventFired"]) == 2

    def test_remove_event_listener(self, client):
        """Test removing a registered listener."""
        callback = AsyncMock()
        client.on_event("Page.loadEventFired", callback)
        client.remove_event_listener("Page.loadEventFired", callback)

        assert callback not in client._event_listeners["Page.loadEventFired"]

    def test_remove_nonexistent_listener(self, client):
        """Test removing a listener that was never registered does not raise."""
        callback = AsyncMock()
        client.remove_event_listener("Page.loadEventFired", callback)


class TestCdpClientReaderLoop:
    """Test the internal reader loop behavior."""

    @pytest.mark.anyio
    async def test_reader_loop_dispatches_response(self, client, mock_ws):
        """Test that reader loop resolves pending futures on response messages."""
        with patch("mindor.core.utils.cdp_client.WebSocketClient", return_value=mock_ws):
            mock_ws.receive_message.side_effect = [
                {"id": 1, "result": {"data": "test"}},
                asyncio.CancelledError,
            ]
            await client.connect()

            result = await client.send_command("Test.method")
            assert result == {"data": "test"}

            await client.close()

    @pytest.mark.anyio
    async def test_reader_loop_dispatches_event(self, client, mock_ws):
        """Test that reader loop calls event listeners on event messages."""
        with patch("mindor.core.utils.cdp_client.WebSocketClient", return_value=mock_ws):
            received_params = {}

            async def on_event(params):
                received_params.update(params)

            client.on_event("Page.loadEventFired", on_event)

            mock_ws.receive_message.side_effect = [
                {"method": "Page.loadEventFired", "params": {"timestamp": 123}},
                asyncio.CancelledError,
            ]
            await client.connect()

            await asyncio.sleep(0.1)

            assert received_params == {"timestamp": 123}

            await client.close()

    @pytest.mark.anyio
    async def test_reader_loop_error_propagation(self, client, mock_ws):
        """Test that reader loop errors propagate to pending futures."""
        with patch("mindor.core.utils.cdp_client.WebSocketClient", return_value=mock_ws):
            mock_ws.receive_message.side_effect = ConnectionError("Connection lost")
            await client.connect()

            loop = asyncio.get_running_loop()
            future = loop.create_future()
            client._pending[99] = future

            await asyncio.sleep(0.1)

            assert future.done()
            with pytest.raises(ConnectionError, match="terminated unexpectedly"):
                future.result()

            await client.close()


class TestCdpClientFromHostPort:
    """Test the from_host_port factory method."""

    @pytest.mark.anyio
    async def test_from_host_port_success(self):
        """Test successful target discovery and connection."""
        targets = [
            {"type": "page", "webSocketDebuggerUrl": "ws://localhost:9222/devtools/page/abc"},
            {"type": "page", "webSocketDebuggerUrl": "ws://localhost:9222/devtools/page/def"},
        ]

        mock_response = AsyncMock()
        mock_response.json = AsyncMock(return_value=targets)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_ws = MagicMock()
        mock_ws.connect = AsyncMock()
        mock_ws.close = AsyncMock()
        mock_ws.receive_message = AsyncMock(side_effect=asyncio.CancelledError)

        with (
            patch("mindor.core.utils.cdp_client.aiohttp.ClientSession", return_value=mock_session),
            patch("mindor.core.utils.cdp_client.WebSocketClient", return_value=mock_ws) as MockWS,
        ):
            client = await CdpClient.from_host_port("localhost", 9222, target_index=0, timeout=5.0)

            assert client.ws_url == "ws://localhost:9222/devtools/page/abc"
            assert client.timeout == 5.0
            MockWS.assert_called_once_with("ws://localhost:9222/devtools/page/abc")
            mock_ws.connect.assert_awaited_once()

            await client.close()

    @pytest.mark.anyio
    async def test_from_host_port_target_index(self):
        """Test selecting a specific target by index."""
        targets = [
            {"type": "page", "webSocketDebuggerUrl": "ws://localhost:9222/devtools/page/first"},
            {"type": "page", "webSocketDebuggerUrl": "ws://localhost:9222/devtools/page/second"},
        ]

        mock_response = AsyncMock()
        mock_response.json = AsyncMock(return_value=targets)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_ws = MagicMock()
        mock_ws.connect = AsyncMock()
        mock_ws.close = AsyncMock()
        mock_ws.receive_message = AsyncMock(side_effect=asyncio.CancelledError)

        with (
            patch("mindor.core.utils.cdp_client.aiohttp.ClientSession", return_value=mock_session),
            patch("mindor.core.utils.cdp_client.WebSocketClient", return_value=mock_ws),
        ):
            client = await CdpClient.from_host_port("localhost", 9222, target_index=1)

            assert client.ws_url == "ws://localhost:9222/devtools/page/second"

            await client.close()

    @pytest.mark.anyio
    async def test_from_host_port_no_page_target(self):
        """Test ConnectionError when no page targets are found."""
        targets = [
            {"type": "service_worker", "webSocketDebuggerUrl": "ws://localhost:9222/devtools/sw/abc"},
        ]

        mock_response = AsyncMock()
        mock_response.json = AsyncMock(return_value=targets)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("mindor.core.utils.cdp_client.aiohttp.ClientSession", return_value=mock_session):
            with pytest.raises(ConnectionError, match="No 'page' target found"):
                await CdpClient.from_host_port("localhost", 9222)

    @pytest.mark.anyio
    async def test_from_host_port_target_index_out_of_range(self):
        """Test IndexError when target_index exceeds available targets."""
        targets = [
            {"type": "page", "webSocketDebuggerUrl": "ws://localhost:9222/devtools/page/only"},
        ]

        mock_response = AsyncMock()
        mock_response.json = AsyncMock(return_value=targets)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("mindor.core.utils.cdp_client.aiohttp.ClientSession", return_value=mock_session):
            with pytest.raises(IndexError, match="out of range"):
                await CdpClient.from_host_port("localhost", 9222, target_index=5)

# ---- Integration Tests (real Chrome, skipped if unavailable) ----

@pytest.mark.skipif(not CHROME_AVAILABLE, reason="Google Chrome not found")
class TestCdpClientIntegrationConnection:
    """Test real CDP connection lifecycle."""

    @pytest.mark.anyio
    async def test_connect_and_close(self, chrome):
        """Test connecting to a real Chrome instance and closing."""
        client = await CdpClient.from_host_port("localhost", chrome["port"], timeout=5.0)

        assert client._ws is not None
        assert client._reader_task is not None

        await client.close()

        assert client._ws is None
        assert client._reader_task is None

    @pytest.mark.anyio
    async def test_from_host_port(self, chrome):
        """Test factory method discovers correct WebSocket URL."""
        client = await CdpClient.from_host_port("localhost", chrome["port"], timeout=5.0)

        assert "ws://" in client.ws_url
        assert "devtools" in client.ws_url

        await client.close()


@pytest.mark.skipif(not CHROME_AVAILABLE, reason="Google Chrome not found")
class TestCdpClientIntegrationCommands:
    """Test real CDP command execution."""

    @pytest.mark.anyio
    async def test_page_navigate(self, chrome):
        """Test Page.navigate command."""
        client = await CdpClient.from_host_port("localhost", chrome["port"], timeout=5.0)

        await client.send_command("Page.enable")
        result = await client.send_command("Page.navigate", {"url": "data:text/html,<h1>Hello</h1>"})

        assert "frameId" in result

        await client.close()

    @pytest.mark.anyio
    async def test_runtime_evaluate(self, chrome):
        """Test Runtime.evaluate command."""
        client = await CdpClient.from_host_port("localhost", chrome["port"], timeout=5.0)

        result = await client.send_command("Runtime.evaluate", {
            "expression": "1 + 2",
            "returnByValue": True,
        })

        assert result["result"]["value"] == 3

        await client.close()

    @pytest.mark.anyio
    async def test_runtime_evaluate_string(self, chrome):
        """Test Runtime.evaluate with string result."""
        client = await CdpClient.from_host_port("localhost", chrome["port"], timeout=5.0)

        result = await client.send_command("Runtime.evaluate", {
            "expression": "'hello' + ' ' + 'world'",
            "returnByValue": True,
        })

        assert result["result"]["value"] == "hello world"

        await client.close()

    @pytest.mark.anyio
    async def test_runtime_evaluate_object(self, chrome):
        """Test Runtime.evaluate with object result."""
        client = await CdpClient.from_host_port("localhost", chrome["port"], timeout=5.0)

        result = await client.send_command("Runtime.evaluate", {
            "expression": "({a: 1, b: 'two'})",
            "returnByValue": True,
        })

        assert result["result"]["value"] == {"a": 1, "b": "two"}

        await client.close()

    @pytest.mark.anyio
    async def test_dom_get_document(self, chrome):
        """Test DOM.getDocument command."""
        client = await CdpClient.from_host_port("localhost", chrome["port"], timeout=5.0)

        await client.send_command("Page.enable")
        await client.send_command("Page.navigate", {"url": "data:text/html,<div id='test'>content</div>"})
        await asyncio.sleep(0.5)

        result = await client.send_command("DOM.getDocument")

        assert "root" in result
        assert result["root"]["nodeName"] == "#document"

        await client.close()

    @pytest.mark.anyio
    async def test_multiple_commands_sequentially(self, chrome):
        """Test sending multiple commands on the same connection."""
        client = await CdpClient.from_host_port("localhost", chrome["port"], timeout=5.0)

        r1 = await client.send_command("Runtime.evaluate", {"expression": "1", "returnByValue": True})
        r2 = await client.send_command("Runtime.evaluate", {"expression": "2", "returnByValue": True})
        r3 = await client.send_command("Runtime.evaluate", {"expression": "3", "returnByValue": True})

        assert r1["result"]["value"] == 1
        assert r2["result"]["value"] == 2
        assert r3["result"]["value"] == 3

        await client.close()


@pytest.mark.skipif(not CHROME_AVAILABLE, reason="Google Chrome not found")
class TestCdpClientIntegrationEvents:
    """Test real CDP event listening."""

    @pytest.mark.anyio
    async def test_page_load_event(self, chrome):
        """Test receiving Page.loadEventFired event."""
        client = await CdpClient.from_host_port("localhost", chrome["port"], timeout=5.0)

        await client.send_command("Page.enable")

        event_received = asyncio.Event()
        event_params = {}

        async def on_load(params):
            event_params.update(params)
            event_received.set()

        client.on_event("Page.loadEventFired", on_load)

        await client.send_command("Page.navigate", {"url": "data:text/html,<h1>Event Test</h1>"})

        await asyncio.wait_for(event_received.wait(), timeout=5.0)

        assert "timestamp" in event_params

        client.remove_event_listener("Page.loadEventFired", on_load)

        await client.close()

    @pytest.mark.anyio
    async def test_page_dom_content_event(self, chrome):
        """Test receiving Page.domContentEventFired event."""
        client = await CdpClient.from_host_port("localhost", chrome["port"], timeout=5.0)

        await client.send_command("Page.enable")

        event_received = asyncio.Event()

        async def on_dom_content(params):
            event_received.set()

        client.on_event("Page.domContentEventFired", on_dom_content)

        await client.send_command("Page.navigate", {"url": "data:text/html,<p>DOM Content</p>"})

        await asyncio.wait_for(event_received.wait(), timeout=5.0)

        assert event_received.is_set()

        await client.close()

    @pytest.mark.anyio
    async def test_remove_event_listener_stops_callback(self, chrome):
        """Test that removed listeners are no longer called."""
        client = await CdpClient.from_host_port("localhost", chrome["port"], timeout=5.0)

        await client.send_command("Page.enable")

        call_count = 0

        async def on_load(params):
            nonlocal call_count
            call_count += 1

        client.on_event("Page.loadEventFired", on_load)

        await client.send_command("Page.navigate", {"url": "data:text/html,<h1>First</h1>"})
        await asyncio.sleep(1.0)
        first_count = call_count

        client.remove_event_listener("Page.loadEventFired", on_load)
        await client.send_command("Page.navigate", {"url": "data:text/html,<h1>Second</h1>"})
        await asyncio.sleep(1.0)

        assert call_count == first_count

        await client.close()


@pytest.mark.skipif(not CHROME_AVAILABLE, reason="Google Chrome not found")
class TestCdpClientIntegrationErrorHandling:
    """Test error handling with real Chrome."""

    @pytest.mark.anyio
    async def test_from_host_port_invalid_port(self):
        """Test ConnectionError on unreachable port."""
        with pytest.raises((ConnectionError, OSError)):
            await CdpClient.from_host_port("localhost", 19999, timeout=2.0)

    @pytest.mark.anyio
    async def test_from_host_port_target_index_out_of_range(self, chrome):
        """Test IndexError when target_index is too large."""
        with pytest.raises(IndexError, match="out of range"):
            await CdpClient.from_host_port("localhost", chrome["port"], target_index=999, timeout=5.0)

    @pytest.mark.anyio
    async def test_invalid_command(self, chrome):
        """Test sending an invalid CDP command."""
        client = await CdpClient.from_host_port("localhost", chrome["port"], timeout=5.0)

        with pytest.raises(RuntimeError, match="CDP error"):
            await client.send_command("NonExistent.method")

        await client.close()

    @pytest.mark.anyio
    async def test_navigate_and_evaluate_after_navigation(self, chrome):
        """Test full navigate → evaluate flow."""
        client = await CdpClient.from_host_port("localhost", chrome["port"], timeout=5.0)

        await client.send_command("Page.enable")

        await client.send_command("Page.navigate", {
            "url": "data:text/html,<div id='target'>Hello CDP</div>"
        })
        await asyncio.sleep(1.0)

        result = await client.send_command("Runtime.evaluate", {
            "expression": "document.getElementById('target').innerText",
            "returnByValue": True,
        })

        assert result["result"]["value"] == "Hello CDP"

        await client.close()
