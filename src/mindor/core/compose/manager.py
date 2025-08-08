from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.compose import ComposeConfig
from mindor.core.controller import ControllerService, TaskState, TaskStatus, create_controller

class ComposeManager:
    def __init__(self, config: ComposeConfig, daemon: bool):
        self.config: ComposeConfig = config
        self.controller: ControllerService = create_controller(
            self.config.controller,
            self.config.workflows,
            self.config.components,
            self.config.listeners,
            self.config.gateways,
            self.config.loggers,
            daemon
        )

    async def launch_services(self, detach: bool, verbose: bool):
        await self.controller.launch_services(detach, verbose)

    async def terminate_services(self, verbose: bool):
        await self.controller.terminate_services(verbose)

    async def start_services(self, verbose: bool):
        await self.controller.start_services(verbose)

    async def stop_services(self, verbose: bool):
        await self.controller.stop_services(verbose)

    async def run_workflow(self, workflow_id: Optional[str], input: Dict[str, Any], output_path: Optional[str], verbose: bool) -> TaskState:
        if not self.controller.started:
            await self.controller.start()

        state = await self.controller.run_workflow(workflow_id, input)

        if output_path and state.status == TaskStatus.COMPLETED:
            await self._save_output(state.output, output_path)
            state.output = None

        return state

    async def _save_output(self, output: Any, path: str) -> None:
        pass
