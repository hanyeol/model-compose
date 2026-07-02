"""Tests for component process runtime, including worker, launcher, and integration scenarios."""

from multiprocessing import Queue

import pytest

from mindor.core.component.base import ComponentGlobalConfigs
from mindor.core.component.component import create_component
from mindor.core.component.runtime.process import ComponentProcessRuntimeLauncher
from mindor.core.component.runtime.process import ComponentProcessRuntimeWorker
from mindor.core.component.runtime.base.ipc_message import IpcMessage, IpcMessageType
from mindor.dsl.schema.action import ShellActionConfig
from mindor.dsl.schema.component.impl.shell import ShellComponentConfig
from mindor.dsl.schema.runtime import ProcessRuntimeConfig


@pytest.fixture
def anyio_backend():
    """Configure anyio to use asyncio backend."""
    return "asyncio"


@pytest.fixture
def global_configs():
    """Fixture for global configs."""
    return ComponentGlobalConfigs(
        components=[],
        listeners=[],
        gateways=[],
        workflows=[]
    )


class TestComponentProcessRuntimeWorker:
    """Test ComponentProcessRuntimeWorker class."""

    def test_worker_initialization(self, global_configs):
        """Test ComponentProcessRuntimeWorker initialization."""
        config = ShellComponentConfig(
            id="test-shell",
            type="shell",
            runtime=ProcessRuntimeConfig(type="process"),
            command=[ "echo", "test" ]
        )

        request_queue = Queue()
        response_queue = Queue()

        worker = ComponentProcessRuntimeWorker(
            "test-shell",
            config,
            global_configs,
            request_queue,
            response_queue
        )

        assert worker.worker_id == "test-shell"
        assert worker.component_config == config
        assert worker.global_configs == global_configs
        assert worker.component is None
        assert worker.running is True


class TestComponentProcessRuntimeLauncher:
    """Test ComponentProcessRuntimeLauncher class."""

    def test_launcher_initialization_with_process_runtime(self, global_configs):
        """Test launcher initialization with process runtime config."""
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

        launcher = ComponentProcessRuntimeLauncher(
            "test-shell",
            config,
            global_configs
        )

        assert launcher.worker_id == "test-shell"
        assert launcher.component_config == config
        assert launcher.global_configs == global_configs
        assert launcher.params.start_timeout == 30.0
        assert launcher.params.stop_timeout == 10.0

    def test_launcher_initialization_with_custom_config(self, global_configs):
        """Test launcher with custom process runtime configuration."""
        config = ShellComponentConfig(
            id="custom-shell",
            type="shell",
            runtime=ProcessRuntimeConfig(
                type="process",
                env={"TEST_VAR": "test_value"},
                start_timeout="2m",
                stop_timeout="30s"
            ),
            command=["echo", "Custom"]
        )

        launcher = ComponentProcessRuntimeLauncher(
            "custom-shell",
            config,
            global_configs
        )

        assert launcher.params.env["TEST_VAR"] == "test_value"
        assert launcher.params.start_timeout == 120.0  # 2m = 120s


class TestComponentIntegration:
    """Integration tests for component with process runtime."""

    def test_create_component_with_process_runtime(self, global_configs):
        """Test creating component with process runtime."""
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
        assert component._process_launcher is None

    @pytest.mark.anyio
    async def test_component_lifecycle(self, global_configs):
        """Test component lifecycle with process runtime."""
        config = ShellComponentConfig(
            id="process-shell",
            type="shell",
            runtime=ProcessRuntimeConfig(
                type="process",
                start_timeout="10s",
                stop_timeout="5s"
            ),
            actions=[
                ShellActionConfig(
                    id="default",
                    command=[ "echo", "Hello from process" ],
                    default=True
                )
            ]
        )

        component = create_component(
            "process-shell",
            config,
            global_configs,
            daemon=False
        )

        await component.setup()
        await component.start()

        # Should have process launcher created
        assert component._process_launcher is not None
        assert isinstance(component._process_launcher, ComponentProcessRuntimeLauncher)
        assert component._process_launcher._runtime.subprocess is not None
        assert component._process_launcher._runtime.subprocess.is_alive()

        # Execute action through process runtime
        result = await component.run(
            action_id="__default__",
            run_id="test-run-1",
            input={}
        )

        assert result is not None
        assert result["stdout"] == "Hello from process"
        assert result["exit_code"] == 0

        await component.stop()

        # Process should be stopped
        assert component._process_launcher._runtime is None

        await component.teardown()

    def test_component_config_with_actions(self, global_configs):
        """Test component with custom actions."""
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
        """Test multiple components with different process runtime configurations."""
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
    """Test various component process runtime scenarios."""

    def test_process_runtime_with_environment_variables(self, global_configs):
        """Test process runtime with environment variables."""
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

        launcher = ComponentProcessRuntimeLauncher(
            "env-test",
            config,
            global_configs
        )

        assert launcher.params.env["CUDA_VISIBLE_DEVICES"] == "0"
        assert launcher.params.env["MODEL_PATH"] == "/models"
        assert launcher.params.env["BATCH_SIZE"] == "32"

    def test_process_runtime_with_timeouts(self, global_configs):
        """Test process runtime with custom timeouts."""
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

        launcher = ComponentProcessRuntimeLauncher(
            "timeout-test",
            config,
            global_configs
        )

        assert launcher.params.start_timeout == 300.0  # 5m = 300s
        assert launcher.params.stop_timeout == 60.0    # 1m = 60s

    def test_process_runtime_with_resource_limits(self, global_configs):
        """Test process runtime with resource limits."""
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

        launcher = ComponentProcessRuntimeLauncher(
            "resource-test",
            config,
            global_configs
        )

        # Resource limits are in ProcessRuntimeConfig but not in ProcessRuntimeParams
        # These are DSL-level configs not used by foundation layer

    def test_component_launcher_attributes(self, global_configs):
        """Test ComponentProcessRuntimeLauncher has correct attributes."""
        config = ShellComponentConfig(
            id="attr-test",
            type="shell",
            runtime=ProcessRuntimeConfig(type="process"),
            command=[ "echo", "test" ]
        )

        launcher = ComponentProcessRuntimeLauncher(
            "attr-test",
            config,
            global_configs
        )

        assert hasattr(launcher, "worker_id")
        assert hasattr(launcher, "component_config")
        assert hasattr(launcher, "global_configs")
        assert hasattr(launcher, "params")
        assert hasattr(launcher, "_runtime")
        assert hasattr(launcher, "_request_queue")
        assert hasattr(launcher, "_response_queue")
        assert hasattr(launcher, "_proxy")
        assert hasattr(launcher, "_channel")

        assert launcher._runtime is None
        assert launcher._request_queue is None
        assert launcher._response_queue is None
        assert launcher._proxy is None
        assert launcher._channel is None


class TestComponentProcessRuntimeValidation:
    """Test validation and error handling."""

    def test_component_id_mismatch(self, global_configs):
        """Test component creation with different IDs."""
        config = ShellComponentConfig(
            id="original-id",
            type="shell",
            runtime=ProcessRuntimeConfig(type="process"),
            command=[ "echo", "test" ]
        )

        launcher = ComponentProcessRuntimeLauncher(
            "different-id",
            config,
            global_configs
        )

        assert launcher.worker_id == "different-id"
        assert launcher.component_config.id == "original-id"

    def test_launcher_run_method_signature(self, global_configs):
        """Test ComponentProcessRuntimeLauncher.run method signature."""
        config = ShellComponentConfig(
            id="run-test",
            type="shell",
            runtime=ProcessRuntimeConfig(type="process"),
            command=[ "echo", "test" ]
        )

        launcher = ComponentProcessRuntimeLauncher(
            "run-test",
            config,
            global_configs
        )

        assert hasattr(launcher, "run")
        assert callable(launcher.run)
