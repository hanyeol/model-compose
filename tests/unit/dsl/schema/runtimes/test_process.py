"""Unit tests for ``ProcessRuntimeConfig``."""

from mindor.dsl.schema.runtime.impl.process import ProcessRuntimeConfig


class TestProcessRuntimeConfig:
    def test_minimal_defaults(self):
        cfg = ProcessRuntimeConfig(type="process")
        assert cfg.start_timeout == "60s"
        assert cfg.stop_timeout == "30s"
        assert cfg.env == {}
        assert cfg.working_dir is None

    def test_full_config(self):
        cfg = ProcessRuntimeConfig(
            type="process",
            env={"KEY": "value"},
            working_dir="/tmp",
            start_timeout=30,
            stop_timeout="15s",
            max_memory="2G",
            cpu_limit=1.5,
        )
        assert cfg.env == {"KEY": "value"}
        assert cfg.max_memory == "2G"
        assert cfg.cpu_limit == 1.5
