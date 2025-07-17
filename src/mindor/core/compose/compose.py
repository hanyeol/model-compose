from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.compose import ComposeConfig
from .manager import ComposeManager, TaskState

async def launch_services(config: ComposeConfig, detach: bool, verbose: bool):
    await ComposeManager(config, daemon=True).launch_services(detach, verbose)

async def shutdown_services(config: ComposeConfig):
    await ComposeManager(config, daemon=False).shutdown_services()

async def start_services(config: ComposeConfig, verbose: bool):
    await ComposeManager(config, daemon=False).start_services(verbose)

async def stop_services(config: ComposeConfig):
    await ComposeManager(config, daemon=False).stop_services()

async def run_workflow(config: ComposeConfig, workflow_id: Optional[str], input: Dict[str, Any], verbose: bool) -> TaskState:
    return await ComposeManager(config, daemon=False).run_workflow(workflow_id, input, verbose)
