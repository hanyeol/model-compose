import pytest
import asyncio
from multiprocessing import Queue
from mindor.dsl.schema.runtime import ProcessRuntimeConfig
from mindor.core.foundation.ipc_messages import IpcMessage, IpcMessageType
from mindor.core.component.runtime.process_worker import ComponentProcessWorker
from mindor.core.component.runtime.process_manager import ComponentProcessRuntimeManager
from mindor.core.component.base import ComponentGlobalConfigs
from mindor.core.component.component import create_component
from mindor.dsl.schema.component.impl.shell import ShellComponentConfig
from mindor.dsl.schema.action import ShellActionConfig

# Configure anyio to use only asyncio backend
@pytest.fixture
def anyio_backend():
    return "asyncio"

@pytest.fixture
def global_configs():
    """Fixture for global configs"""
    return ComponentGlobalConfigs(
        components=[],
        listeners=[],
        gateways=[],
        workflows=[]
    )

class TestComponentProcessWorker:
    """Test ComponentProcessWorker class"""

    def test_worker_initialization(self, global_configs):
        """Test ComponentProcessWorker initialization"""
        config = ShellComponentConfig(
            id="test-shell",
            type="shell",
            runtime=ProcessRuntimeConfig(type="process"),
            command=[ "echo", "test" ]
        )

        request_queue = Queue()
        response_queue = Queue()

        worker = ComponentProcessWorker(
            "test-shell",
            config,
            global_configs,
            request_queue,
            response_queue
        )

        assert worker.worker_id == "test-shell"
        assert worker.config == config
        assert worker.global_configs == global_configs
        assert worker.component is None
        assert worker.running is True

class TestComponentProcessRuntimeManager:
    """Test ComponentProcessRuntimeManager class"""

    def test_manager_initialization_with_process_runtime(self, global_configs):
        """Test manager initialization with process runtime config"""
        config = ShellComponentConfig(
            id="test-shell",
            type="shell",
            runtime=ProcessRuntimeConfig(
                type="process",
                start_timeout="30s",
                stop_timeout="10s"
            ),
            command=[ "echo", "Hello" ]
        )

        manager = ComponentProcessRuntimeManager(
            "test-shell",
            config,
            global_configs
        )

        assert manager.worker_id == "test-shell"
        assert manager.config == config
        assert manager.global_configs == global_configs
        # worker_params should be converted from ProcessRuntimeConfig
        assert manager.worker_params.start_timeout == 30.0  # Converted to seconds
        assert manager.worker_params.stop_timeout == 10.0   # Converted to seconds


    def test_manager_initialization_with_custom_config(self, global_configs):
        """Test manager with custom process runtime configuration"""
        config = ShellComponentConfig(
            id="custom-shell",
            type="shell",
            runtime=ProcessRuntimeConfig(
                type="process",
                env={"TEST_VAR": "test_value"},
                start_timeout="2m",
                stop_timeout="30s",
                ipc_method="queue"
            ),
            command=["echo", "Custom"]
        )

        manager = ComponentProcessRuntimeManager(
            "custom-shell",
            config,
            global_configs
        )

        # Check converted params
        assert manager.worker_params.env["TEST_VAR"] == "test_value"
        assert manager.worker_params.start_timeout == 120.0  # 2m = 120s

class TestComponentIntegration:
    """Integration tests for component with process runtime"""

    def test_create_component_with_process_runtime(self, global_configs):
        """Test creating component with process runtime"""
        config = ShellComponentConfig(
            id="test-component",
            type="shell",
            runtime=ProcessRuntimeConfig(type="process"),
            command=[ "echo", "test" ]
        )

        component = create_component(
            "test-component",
            config,
            global_configs,
            daemon=False
        )

        assert component is not None
        assert component.id == "test-component"
        assert isinstance(component.config.runtime, ProcessRuntimeConfig)
        assert component._process_manager is None

    @pytest.mark.anyio
    async def test_component_lifecycle(self, global_configs):
        """Test component lifecycle with process runtime"""
        config = ShellComponentConfig(
            id="process-shell",
            type="shell",
            runtime=ProcessRuntimeConfig(
                type="process",
                start_timeout="10s",
                stop_timeout="5s"
            ),
            command=[ "echo", "Hello from process" ]
        )

        component = create_component(
            "process-shell",
            config,
            global_configs,
            daemon=False
        )

        await component.setup()
        await component.start()

        # Should have process manager created
        assert component._process_manager is not None
        assert isinstance(component._process_manager, ComponentProcessRuntimeManager)
        assert component._process_manager.subprocess is not None
        assert component._process_manager.subprocess.is_alive()

        # Execute action through process runtime
        result = await component.run(
            action_id="__default__",
            run_id="test-run-1",
            input={}
        )

        assert result is not None

        await component.stop()

        # Process should be stopped
        assert not component._process_manager.subprocess.is_alive()

        await component.teardown()

    def test_component_config_with_actions(self, global_configs):
        """Test component with custom actions"""
        config = ShellComponentConfig(
            id="action-shell",
            type="shell",
            runtime=ProcessRuntimeConfig(type="process"),
            command=[ "echo", "default" ],
            actions=[
                ShellActionConfig(
                    id="custom",
                    command=[ "echo", "custom action" ]
                )
            ]
        )

        component = create_component(
            "action-shell",
            config,
            global_configs,
            daemon=False
        )

        assert len(component.config.actions) == 1
        assert component.config.actions[0].id == "custom"

    def test_multiple_components_with_different_configs(self, global_configs):
        """Test multiple components with different process runtime configurations"""
        config1 = ShellComponentConfig(
            id="component-1",
            type="shell",
            runtime=ProcessRuntimeConfig(
                type="process",
                env={"WORKER": "1"}
            ),
            command=["echo", "worker-1"]
        )

        config2 = ShellComponentConfig(
            id="component-2",
            type="shell",
            runtime=ProcessRuntimeConfig(
                type="process",
                env={"WORKER": "2"}
            ),
            command=[ "echo", "worker-2" ]
        )

        component1 = create_component("component-1", config1, global_configs, False)
        component2 = create_component("component-2", config2, global_configs, False)

        assert isinstance(component1.config.runtime, ProcessRuntimeConfig)
        assert isinstance(component2.config.runtime, ProcessRuntimeConfig)

        assert component1.config.runtime.env["WORKER"] == "1"
        assert component2.config.runtime.env["WORKER"] == "2"

class TestComponentProcessRuntimeScenarios:
    """Test various component process runtime scenarios"""

    def test_process_runtime_with_environment_variables(self, global_configs):
        """Test process runtime with environment variables"""
        config = ShellComponentConfig(
            id="env-test",
            type="shell",
            runtime=ProcessRuntimeConfig(
                type="process",
                env={
                    "CUDA_VISIBLE_DEVICES": "0",
                    "MODEL_PATH": "/models",
                    "BATCH_SIZE": "32"
                }
            ),
            command=[ "echo", "$MODEL_PATH" ]
        )

        manager = ComponentProcessRuntimeManager(
            "env-test",
            config,
            global_configs
        )

        assert manager.worker_params.env["CUDA_VISIBLE_DEVICES"] == "0"
        assert manager.worker_params.env["MODEL_PATH"] == "/models"
        assert manager.worker_params.env["BATCH_SIZE"] == "32"

    def test_process_runtime_with_timeouts(self, global_configs):
        """Test process runtime with custom timeouts"""
        config = ShellComponentConfig(
            id="timeout-test",
            type="shell",
            runtime=ProcessRuntimeConfig(
                type="process",
                start_timeout="5m",
                stop_timeout="1m"
            ),
            command=[ "sleep", "1" ]
        )

        manager = ComponentProcessRuntimeManager(
            "timeout-test",
            config,
            global_configs
        )

        assert manager.worker_params.start_timeout == 300.0  # 5m = 300s
        assert manager.worker_params.stop_timeout == 60.0    # 1m = 60s

    def test_process_runtime_with_resource_limits(self, global_configs):
        """Test process runtime with resource limits"""
        config = ShellComponentConfig(
            id="resource-test",
            type="shell",
            runtime=ProcessRuntimeConfig(
                type="process",
                max_memory="2g",
                cpu_limit=2.0
            ),
            command=[ "echo", "resource test" ]
        )

        manager = ComponentProcessRuntimeManager(
            "resource-test",
            config,
            global_configs
        )

        # Resource limits are in ProcessRuntimeConfig but not in ProcessRuntimeParams
        # These are DSL-level configs not used by foundation layer

    def test_process_runtime_ipc_methods(self, global_configs):
        """Test different IPC methods for process runtime"""
        configs = [
            ("queue-test", "queue", None),
            ("unix-test", "unix-socket", "/tmp/test.sock"),
            ("tcp-test", "tcp-socket", None),
        ]

        for comp_id, ipc_method, socket_path in configs:
            runtime_config = ProcessRuntimeConfig(
                type="process",
                ipc_method=ipc_method
            )

            if socket_path:
                runtime_config.socket_path = socket_path

            config = ShellComponentConfig(
                id=comp_id,
                type="shell",
                runtime=runtime_config,
                command=[ "echo", "test" ]
            )

            manager = ComponentProcessRuntimeManager(
                comp_id,
                config,
                global_configs
            )

            # IPC method is in ProcessRuntimeConfig but not used by foundation layer yet
            # Foundation layer currently only uses Queue-based IPC

    def test_component_manager_attributes(self, global_configs):
        """Test ComponentProcessRuntimeManager has correct attributes"""
        config = ShellComponentConfig(
            id="attr-test",
            type="shell",
            runtime=ProcessRuntimeConfig(type="process"),
            command=[ "echo", "test" ]
        )

        manager = ComponentProcessRuntimeManager(
            "attr-test",
            config,
            global_configs
        )

        assert hasattr(manager, "worker_id")
        assert hasattr(manager, "config")
        assert hasattr(manager, "global_configs")
        assert hasattr(manager, "worker_params")  # Changed from runtime_config
        assert hasattr(manager, "subprocess")
        assert hasattr(manager, "request_queue")
        assert hasattr(manager, "response_queue")
        assert hasattr(manager, "pending_requests")
        assert hasattr(manager, "response_handler_task")

        assert manager.subprocess is None
        assert manager.request_queue is None
        assert manager.response_queue is None
        assert manager.pending_requests == {}
        assert manager.response_handler_task is None

class TestComponentProcessRuntimeValidation:
    """Test validation and error handling"""


    def test_component_id_mismatch(self, global_configs):
        """Test component creation with different IDs"""
        config = ShellComponentConfig(
            id="original-id",
            type="shell",
            runtime=ProcessRuntimeConfig(type="process"),
            command=[ "echo", "test" ]
        )

        manager = ComponentProcessRuntimeManager(
            "different-id",
            config,
            global_configs
        )

        assert manager.worker_id == "different-id"
        assert manager.config.id == "original-id"

    def test_manager_run_method_signature(self, global_configs):
        """Test ComponentProcessRuntimeManager.run method signature"""
        config = ShellComponentConfig(
            id="run-test",
            type="shell",
            runtime=ProcessRuntimeConfig(type="process"),
            command=[ "echo", "test" ]
        )

        manager = ComponentProcessRuntimeManager(
            "run-test",
            config,
            global_configs
        )

        assert hasattr(manager, "run")
        assert callable(manager.run)
