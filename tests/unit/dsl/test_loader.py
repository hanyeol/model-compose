"""Unit tests for ``mindor.dsl.loader.ComposeConfigLoader``.

The full ``load()`` flow is covered indirectly by examples and integration runs;
these tests target the pure helpers ``_resolve_environment_variables`` and
``_merge_config_dict`` plus a happy-path end-to-end load against a tmp file.
"""

from pathlib import Path

import pytest

from mindor.dsl.loader import ComposeConfigLoader, load_compose_config


@pytest.fixture
def loader() -> ComposeConfigLoader:
    return ComposeConfigLoader("model-compose")


class TestResolveEnvironmentVariables:
    def test_replaces_known_variable(self, loader):
        result = loader._resolve_environment_variables("port: ${env.PORT}", {"PORT": "8080"})
        assert result == "port: 8080"

    def test_replaces_with_default_when_missing(self, loader):
        result = loader._resolve_environment_variables("port: ${env.PORT|9090}", {})
        assert result == "port: 9090"

    def test_known_variable_overrides_default(self, loader):
        result = loader._resolve_environment_variables("port: ${env.PORT|9090}", {"PORT": "8080"})
        assert result == "port: 8080"

    def test_unknown_variable_without_default_raises(self, loader):
        with pytest.raises(ValueError, match="Environment variable 'MISSING' is not set"):
            loader._resolve_environment_variables("v: ${env.MISSING}", {})

    def test_multiple_replacements_in_one_string(self, loader):
        result = loader._resolve_environment_variables(
            "${env.HOST}:${env.PORT}", {"HOST": "localhost", "PORT": "8080"}
        )
        assert result == "localhost:8080"

    def test_no_variables_passthrough(self, loader):
        assert loader._resolve_environment_variables("plain text", {}) == "plain text"

    def test_whitespace_around_name(self, loader):
        # Pattern allows leading whitespace inside ${ ... env.NAME }
        result = loader._resolve_environment_variables("${  env.X  }", {"X": "ok"})
        assert result == "ok"


class TestMergeConfigDict:
    def test_top_level_keys_override(self, loader):
        base = {"a": 1, "b": 2}
        override = {"b": 20, "c": 30}
        assert loader._merge_config_dict(base, override) == {"a": 1, "b": 20, "c": 30}

    def test_nested_dicts_deep_merged(self, loader):
        base = {"controller": {"port": 8080, "host": "localhost"}}
        override = {"controller": {"port": 9090}}
        assert loader._merge_config_dict(base, override) == {
            "controller": {"port": 9090, "host": "localhost"}
        }

    def test_lists_are_replaced_not_concatenated(self, loader):
        base = {"items": [1, 2, 3]}
        override = {"items": [4, 5]}
        assert loader._merge_config_dict(base, override) == {"items": [4, 5]}

    def test_does_not_mutate_base(self, loader):
        base = {"a": {"x": 1}}
        loader._merge_config_dict(base, {"a": {"y": 2}})
        assert base == {"a": {"x": 1}}

    def test_dict_vs_scalar_override_wins(self, loader):
        # When types disagree the override wins wholesale (no deep merge).
        base = {"a": {"x": 1}}
        override = {"a": "scalar"}
        assert loader._merge_config_dict(base, override) == {"a": "scalar"}


class TestLoadEndToEnd:
    def _write(self, path: Path, content: str):
        path.write_text(content, encoding="utf-8")

    _MINIMAL = """
controller:
  adapter:
    type: http-server
    port: {port}
"""

    def test_load_resolves_env_and_validates(self, tmp_path, loader):
        config_file = tmp_path / "main.yml"
        self._write(config_file, """
controller:
  adapter:
    type: http-server
    port: ${env.PORT|8080}
""")
        config = loader.load(tmp_path, [config_file], env={})
        assert config.controller.adapters[0].port == 8080

    def test_load_merges_multiple_files(self, tmp_path, loader):
        base = tmp_path / "base.yml"
        override = tmp_path / "override.yml"
        self._write(base, self._MINIMAL.format(port=8080))
        self._write(override, """
controller:
  adapter:
    type: http-server
    port: 9090
""")
        config = loader.load(tmp_path, [base, override], env={})
        assert config.controller.adapters[0].port == 9090

    def test_load_missing_file_raises(self, tmp_path, loader):
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            loader.load(tmp_path, [tmp_path / "ghost.yml"], env={})

    def test_load_invalid_yaml_raises(self, tmp_path, loader):
        bad = tmp_path / "bad.yml"
        self._write(bad, ":\n  this is: ]not yaml")
        with pytest.raises(ValueError, match="YAML parsing error"):
            loader.load(tmp_path, [bad], env={})

    def test_load_auto_discovers_default_file(self, tmp_path, loader):
        self._write(tmp_path / "model-compose.yml", self._MINIMAL.format(port=8080))
        config = loader.load(tmp_path, [], env={})
        assert config.controller.adapters[0].port == 8080

    def test_load_auto_discovery_missing_raises(self, tmp_path, loader):
        with pytest.raises(FileNotFoundError, match="model-compose.yml or .yaml not found"):
            loader.load(tmp_path, [], env={})


class TestLoadComposeConfigShortcut:
    def test_shortcut_uses_default_name(self, tmp_path):
        (tmp_path / "model-compose.yml").write_text("""
controller:
  adapter:
    type: http-server
    port: 8080
""", encoding="utf-8")
        config = load_compose_config(tmp_path, [], env={})
        assert config.controller.adapters[0].port == 8080
