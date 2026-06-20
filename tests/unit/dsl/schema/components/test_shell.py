"""Unit tests for ``ShellComponentConfig`` schema validation."""

from mindor.dsl.schema.component.impl.shell import ShellComponentConfig


class TestManageScripts:
    """Inline ``install``/``clean`` keys are lifted into ``manage.scripts``;
    single-command script lists are wrapped into list-of-lists. Unlike server
    components, shell components have no ``build``/``start`` lifecycle."""

    def test_single_install_command_wrapped(self):
        cfg = ShellComponentConfig.model_validate({"type": "shell", "install": ["pip", "install", "x"]})
        assert cfg.manage.scripts.install == [["pip", "install", "x"]]

    def test_clean_command_wrapped(self):
        cfg = ShellComponentConfig.model_validate({"type": "shell", "clean": ["rm", "-rf", "dist"]})
        assert cfg.manage.scripts.clean == [["rm", "-rf", "dist"]]
