"""Unit tests for ``DockerComposeSystemConfig`` schema validation."""

from mindor.dsl.schema.system.impl.docker_compose import DockerComposeSystemConfig


class TestFileShorthand:
    """Top-level ``file`` is a shorthand for a single-item ``files`` list."""

    def test_single_file_inflated_to_files_list(self):
        cfg = DockerComposeSystemConfig.model_validate({
            "type": "docker-compose",
            "file": "docker-compose.yml",
        })
        assert cfg.files == ["docker-compose.yml"]

    def test_explicit_files_list_pass_through(self):
        cfg = DockerComposeSystemConfig.model_validate({
            "type": "docker-compose",
            "files": ["a.yml", "b.yml"],
        })
        assert cfg.files == ["a.yml", "b.yml"]

    def test_no_file_or_files_yields_empty_list(self):
        cfg = DockerComposeSystemConfig.model_validate({"type": "docker-compose"})
        assert cfg.files == []
