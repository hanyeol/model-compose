from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.compose import ComposeConfig
from .manager import ComposeManager, TaskState

async def launch_services(config: ComposeConfig, detach: bool, env: Dict[str, str]):
    await ComposeManager(config, env, daemon=True).launch_services(detach=detach)

async def shutdown_services(config: ComposeConfig, env: Dict[str, str]):
    await ComposeManager(config, env, daemon=False).shutdown_services()

async def start_services(config: ComposeConfig, detach: bool, env: Dict[str, str]):
    await ComposeManager(config, env, daemon=False).start_services()

async def stop_services(config: ComposeConfig, env: Dict[str, str]):
    await ComposeManager(config, env, daemon=False).stop_services()

async def run_workflow(config: ComposeConfig, workflow_id: Optional[str], input: Dict[str, Any], env: Dict[str, str]) -> TaskState:
    return await ComposeManager(config, env, daemon=False).run_workflow(workflow_id, input)
