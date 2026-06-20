"""Unit tests for ``WebSocketServerComponentConfig`` schema validation."""

from mindor.dsl.schema.component.impl.websocket_server import WebSocketServerComponentConfig


class TestManageScripts:
    """Inline script keys are lifted into ``manage.scripts``; single-command
    script lists are wrapped into list-of-lists."""

    def test_single_install_command_wrapped(self):
        cfg = WebSocketServerComponentConfig.model_validate({"type": "websocket-server", "install": ["pip", "install", "x"]})
        assert cfg.manage.scripts.install == [["pip", "install", "x"]]

    def test_multiple_build_commands_pass_through(self):
        cfg = WebSocketServerComponentConfig.model_validate({
            "type": "websocket-server",
            "build": [["npm", "ci"], ["npm", "run", "build"]],
        })
        assert cfg.manage.scripts.build == [["npm", "ci"], ["npm", "run", "build"]]

    def test_start_is_a_single_command_not_a_list_of_commands(self):
        cfg = WebSocketServerComponentConfig.model_validate({
            "type": "websocket-server",
            "start": ["python", "main.py"],
        })
        assert cfg.manage.scripts.start == ["python", "main.py"]

    def test_inline_keys_lifted_into_manage_block(self):
        cfg = WebSocketServerComponentConfig.model_validate({
            "type": "websocket-server",
            "install": ["pip", "install", "x"],
            "start": ["python", "main.py"],
        })
        assert cfg.manage.scripts.install == [["pip", "install", "x"]]
        assert cfg.manage.scripts.start == ["python", "main.py"]

    def test_explicit_manage_block_pass_through(self):
        cfg = WebSocketServerComponentConfig.model_validate({
            "type": "websocket-server",
            "manage": {
                "scripts": {"install": [["a"]], "start": ["b"]},
                "working_dir": "/tmp",
            },
        })
        assert cfg.manage.working_dir == "/tmp"
        assert cfg.manage.scripts.install == [["a"]]
