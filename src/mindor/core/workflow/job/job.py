from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from mindor.dsl.schema.workflow import JobConfig
from mindor.dsl.schema.component import ComponentConfig
from .impl import Job, JobMap

def create_job(id: str, config: JobConfig, components: Dict[str, ComponentConfig]) -> Job:
    return JobMap[config.type](id, config, components)
