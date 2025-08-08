from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.component import ShellComponentConfig
from mindor.dsl.schema.action import ActionConfig, ShellActionConfig
from mindor.core.utils.shell import run_command_streaming, run_command
from ..base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ..context import ComponentActionContext
import os

class ShellAction:
    def __init__(self, config: ShellActionConfig, base_dir: Optional[str], env: Optional[Dict[str, str]]):
        self.config: ShellActionConfig = config
        self.base_dir: Optional[str] = base_dir
        self.env: Optional[Dict[str, str]] = env

    async def run(self, context: ComponentActionContext) -> Any:
        working_dir = await self._resolve_working_directory()
        env = await context.render_variable({ **(self.env or {}), **(self.config.env or {}) })

        result = await self._run_command(self.config.command, working_dir, env, self.config.timeout)
        context.register_source("result", result)

        return (await context.render_variable(self.config.output, ignore_files=True)) if self.config.output else result
    
    async def _run_command(self, command: List[str], working_dir: str, env: Dict[str, str], timeout: Optional[float]) -> Dict[str, Any]:
        stdout, stderr, exit_code = await run_command(command, working_dir, env, timeout)

        return {
            "stdout": stdout.decode().strip(),
            "stderr": stderr.decode().strip(),
            "exit_code": exit_code
        }

    async def _resolve_working_directory(self) -> str:
        working_dir = self.config.working_dir

        if working_dir:
            if self.base_dir:
                working_dir = os.path.abspath(os.path.join(self.base_dir, working_dir))
            else:
                working_dir = os.path.abspath(working_dir)
        else:
            working_dir = self.base_dir or os.getcwd()

        return working_dir

@register_component(ComponentType.SHELL)
class ShellComponent(ComponentService):
    def __init__(self, id: str, config: ShellComponentConfig, global_configs: ComponentGlobalConfigs, daemon: bool):
        super().__init__(id, config, global_configs, daemon)

    async def _setup(self) -> None:
        if self.config.manage.scripts.install:
            for command in self.config.manage.scripts.install:
                await run_command_streaming(command, self.config.manage.working_dir, self.config.manage.env)

    async def _teardown(self):
        if self.config.manage.scripts.clean:
            for command in self.config.manage.scripts.clean:
                await run_command_streaming(command, self.config.manage.working_dir, self.config.manage.env)

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return await ShellAction(action, self.config.base_dir, self.config.env).run(context)
