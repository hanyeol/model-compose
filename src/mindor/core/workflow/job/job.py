from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from mindor.dsl.schema.workflow import JobConfig
from mindor.dsl.schema.component import ComponentConfig
from .base import Job, JobRegistry

def create_job(id: str, config: JobConfig, components: Dict[str, ComponentConfig]) -> Job:
    if not JobRegistry:
        from . import impl
    return JobRegistry[config.type](id, config, components)
