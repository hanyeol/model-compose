from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from mindor.dsl.schema.workflow import JobConfig
from mindor.dsl.schema.component import ComponentConfig
from mindor.core.component import ComponentGlobalConfigs
from .base import Job, JobRegistry, RoutingTarget

def create_job(id: str, config: JobConfig, global_configs: ComponentGlobalConfigs) -> Job:
    if not JobRegistry:
        from . import impl
    return JobRegistry[config.type](id, config, global_configs)
