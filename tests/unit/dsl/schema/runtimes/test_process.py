"""Unit tests for ``ProcessRuntimeConfig`` and the ``IpcMethod`` enum."""

import pytest
from pydantic import ValidationError

from mindor.dsl.schema.runtime.impl.process import IpcMethod, ProcessRuntimeConfig


class TestProcessRuntimeConfig:
    def test_minimal_defaults(self):
        cfg = ProcessRuntimeConfig(type="process")
        assert cfg.ipc_method == IpcMethod.QUEUE
        assert cfg.start_timeout == "60s"
        assert cfg.stop_timeout == "30s"
        assert cfg.env == {}
        assert cfg.working_dir is None
        assert cfg.socket_path is None
        assert cfg.tcp_port is None

    def test_full_config(self):
        cfg = ProcessRuntimeConfig(
            type="process",
            env={"KEY": "value"},
            working_dir="/tmp",
            start_timeout=30,
            stop_timeout="15s",
            ipc_method="tcp-socket",
            tcp_port=5000,
            max_memory="2G",
            cpu_limit=1.5,
        )
        assert cfg.env == {"KEY": "value"}
        assert cfg.ipc_method == IpcMethod.TCP_SOCKET
        assert cfg.tcp_port == 5000
        assert cfg.max_memory == "2G"
        assert cfg.cpu_limit == 1.5


class TestIpcMethod:
    @pytest.mark.parametrize("method,enum_value", [
        ("queue", IpcMethod.QUEUE),
        ("unix-socket", IpcMethod.UNIX_SOCKET),
        ("named-pipe", IpcMethod.NAMED_PIPE),
        ("tcp-socket", IpcMethod.TCP_SOCKET),
    ])
    def test_ipc_method_values(self, method, enum_value):
        cfg = ProcessRuntimeConfig(type="process", ipc_method=method)
        assert cfg.ipc_method == enum_value

    def test_invalid_ipc_method_rejected(self):
        with pytest.raises(ValidationError):
            ProcessRuntimeConfig(type="process", ipc_method="invalid-ipc")
