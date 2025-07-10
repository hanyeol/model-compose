from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.compose import ComposeConfig
from mindor.core.controller import ControllerEngine, TaskState, create_controller

class ComposeManager:
    def __init__(self, config: ComposeConfig, daemon: bool = True):
        self.config: ComposeConfig = config
        self.controller: ControllerEngine = create_controller(
            self.config.controller,
            self.config.components,
            self.config.listeners,
            self.config.gateways,
            self.config.workflows,
            daemon
        )

    async def launch_services(self, detach: bool, background: bool = False):
        await self.controller.start(background=background)
        await self.controller.wait_until_stopped()

    async def shutdown_services(self):
        await self.controller.stop()

    async def start_services(self, background: bool = False):
        await self.controller.start(background=background)
        await self.controller.wait_until_stopped()

    async def stop_services(self):
        await self.controller.stop()

    async def run_workflow(self, workflow_id: Optional[str], input: Dict[str, Any]) -> TaskState:
        if not self.controller.started:
            await self.controller.start()

        return await self.controller.run_workflow(workflow_id, input)
