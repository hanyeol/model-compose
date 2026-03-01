from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.compose import ComposeConfig

if TYPE_CHECKING:
    from .manager import TaskState

async def launch_services(config: ComposeConfig, detach: bool, verbose: bool):
    from .manager import ComposeManager
    await ComposeManager(config, daemon=True).launch_services(detach, verbose)

async def terminate_services(config: ComposeConfig, verbose: bool):
    from .manager import ComposeManager
    await ComposeManager(config, daemon=False).terminate_services(verbose)

async def start_services(config: ComposeConfig, verbose: bool):
    from .manager import ComposeManager
    await ComposeManager(config, daemon=True).start_services(verbose)

async def stop_services(config: ComposeConfig, verbose: bool):
    from .manager import ComposeManager
    await ComposeManager(config, daemon=False).stop_services(verbose)

async def run_workflow(config: ComposeConfig, workflow_id: str, input: Dict[str, Any], output_path: Optional[str], verbose: bool) -> TaskState:
    from .manager import ComposeManager
    return await ComposeManager(config, daemon=False).run_workflow(workflow_id, input, output_path, verbose)

def validate_compose_config(config: ComposeConfig) -> List[str]:
    from .validator import ComposeValidator
    return ComposeValidator(config).validate()
