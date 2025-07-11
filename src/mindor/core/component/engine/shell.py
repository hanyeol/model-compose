from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.component import ShellComponentConfig
from mindor.dsl.schema.action import ActionConfig, ShellActionConfig
from .base import ComponentEngine, ComponentType, ComponentEngineMap, ActionConfig
from .context import ComponentActionContext
from asyncio.subprocess import Process
import asyncio, os

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
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=working_dir,
            env={ **os.environ, **env },
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            if await self._kill_process(process):
                raise RuntimeError(f"Command timed out: {' '.join(command)}")

        return { 
            "stdout": stdout.decode().strip(), 
            "stderr": stderr.decode().strip(),
            "exit_code": process.returncode
        }

    async def _kill_process(self, process: Process) -> bool:
        if process.returncode is None:
            process.kill()
            try:
                await process.wait()
            except Exception as e:
                pass
            return True
        else:
            return False

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

class ShellComponent(ComponentEngine):
    def __init__(self, id: str, config: ShellComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _serve(self) -> None:
        pass

    async def _shutdown(self) -> None:
        pass

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return await ShellAction(action, self.config.base_dir, self.config.env).run(context)

ComponentEngineMap[ComponentType.SHELL] = ShellComponent
