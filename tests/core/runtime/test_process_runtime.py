import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from multiprocessing import Queue
from mindor.dsl.schema.runtime import ProcessRuntimeConfig, EmbeddedRuntimeConfig
from mindor.dsl.schema.runtime.impl.process import IpcMethod
from mindor.core.foundation.ipc_messages import IpcMessage, IpcMessageType
from mindor.core.foundation.process_worker import ProcessWorker, ProcessWorkerParams
from mindor.core.foundation.process_manager import ProcessRuntimeManager
from mindor.core.component.runtime.process_worker import ComponentProcessWorker
from mindor.core.component.runtime.process_manager import ComponentProcessRuntimeManager
from mindor.core.component.base import ComponentGlobalConfigs
from mindor.dsl.schema.component.impl.shell import ShellComponentConfig


# Configure anyio to use only asyncio backend
@pytest.fixture
def anyio_backend():
    return "asyncio"


# Module-level worker factories for pickling support
class MathWorker(ProcessWorker):
    """Worker for math operations"""
    async def _initialize(self):
        pass

    async def _execute_task(self, payload):
        operation = payload.get("operation")
        a = payload.get("a", 0)
        b = payload.get("b", 0)

        if operation == "add":
            return { "result": a + b }
        elif operation == "multiply":
            return { "result": a * b }
        else:
            return { "error": "Unknown operation" }

    async def _cleanup(self):
        pass


class CounterWorker(ProcessWorker):
    """Worker that counts invocations"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.count = 0

    async def _initialize(self):
        self.count = 0

    async def _execute_task(self, payload):
        self.count += 1
        return { "count": self.count, "message": payload.get("message", "") }

    async def _cleanup(self):
        pass


class ErrorWorker(ProcessWorker):
    """Worker that can raise errors"""
    async def _initialize(self):
        pass

    async def _execute_task(self, payload):
        if payload.get("should_fail"):
            raise ValueError("Intentional error for testing")
        return { "status": "success" }

    async def _cleanup(self):
        pass


def create_math_worker(worker_id, req_queue, res_queue):
    """Factory function for MathWorker"""
    return MathWorker(worker_id, req_queue, res_queue)


def create_counter_worker(worker_id, req_queue, res_queue):
    """Factory function for CounterWorker"""
    return CounterWorker(worker_id, req_queue, res_queue)


def create_error_worker(worker_id, req_queue, res_queue):
    """Factory function for ErrorWorker"""
    return ErrorWorker(worker_id, req_queue, res_queue)


@pytest.fixture
def global_configs():
    """Fixture for global configs"""
    return ComponentGlobalConfigs(
        components=[],
        listeners=[],
        gateways=[],
        workflows=[]
    )


class TestProcessRuntimeConfig:
    """Test ProcessRuntimeConfig schema"""

    def test_minimal_config(self):
        """Test minimal configuration with defaults"""
        config = ProcessRuntimeConfig(type="process")

        assert config.type == "process"
        assert config.env == {}
        assert config.working_dir is None
        assert config.start_timeout == "60s"
        assert config.stop_timeout == "30s"
        assert config.ipc_method == IpcMethod.QUEUE
        assert config.socket_path is None
        assert config.pipe_name is None
        assert config.tcp_port is None
        assert config.max_memory is None
        assert config.cpu_limit is None

    def test_config_with_environment_variables(self):
        """Test configuration with environment variables"""
        config = ProcessRuntimeConfig(
            type="process",
            env={
                "CUDA_VISIBLE_DEVICES": "0",
                "PYTORCH_CUDA_ALLOC_CONF": "max_split_size_mb:512",
                "TEST_VAR": "test_value"
            }
        )

        assert config.type == "process"
        assert config.env["CUDA_VISIBLE_DEVICES"] == "0"
        assert config.env["PYTORCH_CUDA_ALLOC_CONF"] == "max_split_size_mb:512"
        assert config.env["TEST_VAR"] == "test_value"
        assert len(config.env) == 3

    def test_config_with_custom_timeouts(self):
        """Test configuration with custom timeout values"""
        config = ProcessRuntimeConfig(
            type="process",
            start_timeout="2m",
            stop_timeout="10s"
        )

        assert config.start_timeout == "2m"
        assert config.stop_timeout == "10s"

    def test_config_with_working_directory(self):
        """Test configuration with working directory"""
        config = ProcessRuntimeConfig(
            type="process",
            working_dir="/app/workspace"
        )

        assert config.working_dir == "/app/workspace"

    def test_config_with_queue_ipc(self):
        """Test configuration with queue IPC method (default)"""
        config = ProcessRuntimeConfig(
            type="process",
            ipc_method=IpcMethod.QUEUE
        )

        assert config.ipc_method == IpcMethod.QUEUE
        assert config.socket_path is None
        assert config.pipe_name is None
        assert config.tcp_port is None

    def test_config_with_unix_socket_ipc(self):
        """Test configuration with unix socket IPC method"""
        config = ProcessRuntimeConfig(
            type="process",
            ipc_method=IpcMethod.UNIX_SOCKET,
            socket_path="/tmp/model-compose.sock"
        )

        assert config.ipc_method == IpcMethod.UNIX_SOCKET
        assert config.socket_path == "/tmp/model-compose.sock"

    def test_config_with_named_pipe_ipc(self):
        """Test configuration with named pipe IPC method"""
        config = ProcessRuntimeConfig(
            type="process",
            ipc_method=IpcMethod.NAMED_PIPE,
            pipe_name=r"\\.\pipe\model-compose"
        )

        assert config.ipc_method == IpcMethod.NAMED_PIPE
        assert config.pipe_name == r"\\.\pipe\model-compose"

    def test_config_with_tcp_socket_ipc(self):
        """Test configuration with TCP socket IPC method"""
        config = ProcessRuntimeConfig(
            type="process",
            ipc_method=IpcMethod.TCP_SOCKET,
            tcp_port=9999
        )

        assert config.ipc_method == IpcMethod.TCP_SOCKET
        assert config.tcp_port == 9999

    def test_config_with_resource_limits(self):
        """Test configuration with resource limits"""
        config = ProcessRuntimeConfig(
            type="process",
            max_memory="2g",
            cpu_limit=2.5
        )

        assert config.max_memory == "2g"
        assert config.cpu_limit == 2.5

    def test_full_configuration(self):
        """Test comprehensive configuration"""
        config = ProcessRuntimeConfig(
            type="process",
            env={
                "CUDA_VISIBLE_DEVICES": "0,1",
                "MODEL_PATH": "/models"
            },
            working_dir="/workspace",
            start_timeout="5m",
            stop_timeout="1m",
            ipc_method=IpcMethod.UNIX_SOCKET,
            socket_path="/tmp/worker.sock",
            max_memory="4g",
            cpu_limit=4.0
        )

        assert config.type == "process"
        assert len(config.env) == 2
        assert config.working_dir == "/workspace"
        assert config.start_timeout == "5m"
        assert config.stop_timeout == "1m"
        assert config.ipc_method == IpcMethod.UNIX_SOCKET
        assert config.socket_path == "/tmp/worker.sock"
        assert config.max_memory == "4g"
        assert config.cpu_limit == 4.0


class TestEmbeddedRuntimeConfig:
    """Test EmbeddedRuntimeConfig schema"""

    def test_minimal_config(self):
        """Test minimal embedded runtime configuration"""
        config = EmbeddedRuntimeConfig(type="embedded")

        assert config.type == "embedded"

    def test_type_validation(self):
        """Test type field validation"""
        config = EmbeddedRuntimeConfig(type="embedded")

        assert config.type == "embedded"


class TestIpcProtocol:
    """Test IPC protocol message format"""

    def test_ipc_message_types(self):
        """Test all IPC message types"""
        assert IpcMessageType.START == "start"
        assert IpcMessageType.STOP == "stop"
        assert IpcMessageType.RUN == "run"
        assert IpcMessageType.RESULT == "result"
        assert IpcMessageType.ERROR == "error"
        assert IpcMessageType.HEARTBEAT == "heartbeat"
        assert IpcMessageType.STATUS == "status"
        assert IpcMessageType.LOG == "log"

    def test_ipc_message_creation(self):
        """Test IPC message creation"""
        message = IpcMessage(
            type=IpcMessageType.RUN,
            request_id="test-123",
            payload={ "action": "generate", "input": {"prompt": "hello"} }
        )

        assert message.type == IpcMessageType.RUN
        assert message.request_id == "test-123"
        assert message.payload["action"] == "generate"
        assert message.payload["input"]["prompt"] == "hello"
        assert message.timestamp > 0

    def test_ipc_message_without_payload(self):
        """Test IPC message without payload"""
        message = IpcMessage(
            type=IpcMessageType.HEARTBEAT,
            request_id="heartbeat-1"
        )

        assert message.type == IpcMessageType.HEARTBEAT
        assert message.request_id == "heartbeat-1"
        assert message.payload is None

    def test_ipc_message_serialization(self):
        """Test IPC message serialization"""
        message = IpcMessage(
            type=IpcMessageType.RESULT,
            request_id="req-456",
            payload={ "status": "ready" }
        )

        data = message.to_params()

        assert data["type"] == "result"
        assert data["request_id"] == "req-456"
        assert data["payload"]["status"] == "ready"
        assert "timestamp" in data

    def test_ipc_message_deserialization(self):
        """Test IPC message deserialization"""
        data = {
            "type": "run",
            "request_id": "req-789",
            "payload": {"task": "test"},
            "timestamp": 1234567890
        }

        message = IpcMessage(**data)

        assert message.type == IpcMessageType.RUN
        assert message.request_id == "req-789"
        assert message.payload["task"] == "test"
        assert message.timestamp == 1234567890


class TestProcessWorkerParams:
    """Test ProcessWorkerParams data model"""

    def test_default_params(self):
        """Test default parameter values"""
        params = ProcessWorkerParams()

        assert params.env == {}
        assert params.start_timeout == 60.0
        assert params.stop_timeout == 30.0

    def test_custom_params(self):
        """Test custom parameter values"""
        params = ProcessWorkerParams(
            env={"TEST": "value"},
            start_timeout=120.0,
            stop_timeout=60.0
        )

        assert params.env == {"TEST": "value"}
        assert params.start_timeout == 120.0
        assert params.stop_timeout == 60.0


class TestProcessWorker:
    """Test ProcessWorker base class"""

    def test_worker_initialization(self):
        """Test worker initialization"""
        request_queue = MagicMock(spec=Queue)
        response_queue = MagicMock(spec=Queue)

        # Create a concrete implementation for testing
        class TestWorker(ProcessWorker):
            async def _initialize(self):
                pass

            async def _execute_task(self, payload):
                return { "result": "success" }

            async def _cleanup(self):
                pass

        worker = TestWorker("test-worker", request_queue, response_queue)

        assert worker.worker_id == "test-worker"
        assert worker.request_queue == request_queue
        assert worker.response_queue == response_queue
        assert worker.running is True


class TestComponentProcessRuntimeManager:
    """Test ComponentProcessRuntimeManager"""

    def test_manager_initialization(self, global_configs):
        """Test manager initialization with valid config"""
        config = ShellComponentConfig(
            id="test-shell",
            type="shell",
            runtime=ProcessRuntimeConfig(type="process"),
            command=[ "echo", "test" ]
        )

        manager = ComponentProcessRuntimeManager(
            "test-shell",
            config,
            global_configs
        )

        assert manager.worker_id == "test-shell"
        assert manager.config == config
        assert manager.global_configs == global_configs
        assert isinstance(manager.worker_params, ProcessWorkerParams)

    def test_manager_initialization_with_invalid_runtime(self, global_configs):
        """Test manager initialization fails with non-process runtime"""
        config = ShellComponentConfig(
            id="test-shell",
            type="shell",
            runtime=EmbeddedRuntimeConfig(type="embedded"),
            command=[ "echo", "test" ]
        )

        with pytest.raises(ValueError, match="requires ProcessRuntimeConfig"):
            ComponentProcessRuntimeManager(
                "test-shell",
                config,
                global_configs
            )


class TestIntegration:
    """Integration tests for process runtime"""

    def test_process_runtime_config_in_component(self, global_configs):
        """Test process runtime config can be used in component"""
        config = ShellComponentConfig(
            id="test-component",
            type="shell",
            runtime=ProcessRuntimeConfig(
                type="process",
                env={ "TEST": "value" },
                start_timeout="30s"
            ),
            command=[ "echo", "test" ]
        )

        assert config.runtime.type == "process"
        assert config.runtime.env["TEST"] == "value"
        assert config.runtime.start_timeout == "30s"

    def test_embedded_runtime_config_in_component(self, global_configs):
        """Test embedded runtime config can be used in component"""
        config = ShellComponentConfig(
            id="test-component",
            type="shell",
            runtime=EmbeddedRuntimeConfig(type="embedded"),
            command=[ "echo", "test" ]
        )

        assert config.runtime.type == "embedded"

    def test_multiple_process_configs(self, global_configs):
        """Test multiple components with different process configs"""
        config1 = ShellComponentConfig(
            id="component-1",
            type="shell",
            runtime=ProcessRuntimeConfig(
                type="process",
                env={"DEVICE": "cpu"}
            ),
            command=["echo", "cpu"]
        )

        config2 = ShellComponentConfig(
            id="component-2",
            type="shell",
            runtime=ProcessRuntimeConfig(
                type="process",
                env={ "DEVICE": "cuda:0" }
            ),
            command=[ "echo", "gpu" ]
        )

        assert config1.runtime.env["DEVICE"] == "cpu"
        assert config2.runtime.env["DEVICE"] == "cuda:0"
        assert config1.runtime.type == config2.runtime.type == "process"


class TestIpcCommunication:
    """Test actual IPC communication between processes"""

    @pytest.mark.anyio
    async def test_process_worker_lifecycle(self):
        """Test process worker initialization and cleanup"""
        request_queue = Queue()
        response_queue = Queue()

        class SimpleWorker(ProcessWorker):
            def __init__(self, worker_id, request_queue, response_queue):
                super().__init__(worker_id, request_queue, response_queue)
                self.initialized = False

            async def _initialize(self):
                self.initialized = True

            async def _execute_task(self, payload):
                return { "result": payload.get("value", 0) * 2 }

            async def _cleanup(self):
                self.initialized = False

        worker = SimpleWorker("test-worker", request_queue, response_queue)

        assert worker.worker_id == "test-worker"
        assert worker.running is True
        assert worker.initialized is False

    @pytest.mark.anyio
    async def test_process_runtime_manager_lifecycle(self):
        """Test ProcessRuntimeManager start and stop"""
        params = ProcessWorkerParams(
            start_timeout=5.0,
            stop_timeout=5.0
        )

        manager = ProcessRuntimeManager(
            "test-worker",
            create_math_worker,
            params
        )

        assert manager.worker_id == "test-worker"
        assert manager.subprocess is None

        await manager.start()

        assert manager.subprocess is not None
        assert manager.subprocess.is_alive()

        await asyncio.sleep(0.5)

        await manager.stop()

        assert not manager.subprocess.is_alive()

    @pytest.mark.anyio
    async def test_process_runtime_manager_execute_task(self):
        """Test executing tasks through ProcessRuntimeManager"""
        params = ProcessWorkerParams(
            start_timeout=5.0,
            stop_timeout=5.0
        )

        manager = ProcessRuntimeManager(
            "math-worker",
            create_math_worker,
            params
        )

        await manager.start()

        try:
            result1 = await manager.execute({ "operation": "add", "a": 5, "b": 3})
            assert result1["result"] == 8

            result2 = await manager.execute({ "operation": "multiply", "a": 4, "b": 7 })
            assert result2["result"] == 28

        finally:
            await manager.stop()

    @pytest.mark.anyio
    async def test_process_runtime_manager_multiple_tasks(self):
        """Test executing multiple tasks sequentially"""
        params = ProcessWorkerParams()
        manager = ProcessRuntimeManager("counter-worker", create_counter_worker, params)

        await manager.start()

        try:
            result1 = await manager.execute({ "message": "first" })
            assert result1["count"] == 1
            assert result1["message"] == "first"

            result2 = await manager.execute({ "message": "second" })
            assert result2["count"] == 2
            assert result2["message"] == "second"

            result3 = await manager.execute({ "message": "third" })
            assert result3["count"] == 3
            assert result3["message"] == "third"

        finally:
            await manager.stop()

    @pytest.mark.anyio
    async def test_ipc_message_roundtrip(self):
        """Test IPC message serialization and deserialization through queues"""
        message_queue = Queue()

        original_message = IpcMessage(
            type=IpcMessageType.RUN,
            request_id="test-req-123",
            payload={
                "action": "generate",
                "input": { "prompt": "Hello, world!" },
                "metadata": { "user_id": "user-456" }
            }
        )

        # Serialize and put into queue
        message_queue.put(original_message.to_params())

        # Deserialize from queue
        message_dict = message_queue.get(timeout=1)
        received_message = IpcMessage(**message_dict)

        assert received_message.type == original_message.type
        assert received_message.request_id == original_message.request_id
        assert received_message.payload == original_message.payload
        assert received_message.timestamp == original_message.timestamp

    @pytest.mark.anyio
    async def test_process_worker_error_handling(self):
        """Test error handling in process worker"""
        params = ProcessWorkerParams()
        manager = ProcessRuntimeManager("error-worker", create_error_worker, params)

        await manager.start()

        try:
            success_result = await manager.execute({ "should_fail": False })
            assert success_result["status"] == "success"

            with pytest.raises(Exception, match="Intentional error"):
                await manager.execute({ "should_fail": True })

        finally:
            await manager.stop()

    @pytest.mark.anyio
    async def test_concurrent_process_managers(self):
        """Test multiple ProcessRuntimeManagers running concurrently"""
        params = ProcessWorkerParams()

        manager1 = ProcessRuntimeManager("worker-1", create_math_worker, params)
        manager2 = ProcessRuntimeManager("worker-2", create_counter_worker, params)
        manager3 = ProcessRuntimeManager("worker-3", create_error_worker, params)

        await manager1.start()
        await manager2.start()
        await manager3.start()

        try:
            result1, result2, result3 = await asyncio.gather(
                manager1.execute({ "operation": "add", "a": 10, "b": 20 }),
                manager2.execute({ "message": "hello" }),
                manager3.execute({ "should_fail": False })
            )

            assert result1["result"] == 30
            assert result2["count"] == 1
            assert result3["status"] == "success"

        finally:
            await asyncio.gather(
                manager1.stop(),
                manager2.stop(),
                manager3.stop()
            )
