from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import Field
from .component import ComponentJobConfig
from .loop import LoopJobConfig
from .for_each import ForEachJobConfig
from .accumulate import AccumulateJobConfig
from .pipeline import PipelineJobConfig

InlineJobConfig = Annotated[
    Union[
        ComponentJobConfig,
        LoopJobConfig,
        ForEachJobConfig,
        AccumulateJobConfig,
        PipelineJobConfig,
    ],
    Field(discriminator="type"),
]

# The configs above reference `InlineJobConfig` as a forward string;
# rebuild them here so pydantic resolves that reference against the union just defined.
LoopJobConfig.model_rebuild(_types_namespace={ "InlineJobConfig": InlineJobConfig })
ForEachJobConfig.model_rebuild(_types_namespace={ "InlineJobConfig": InlineJobConfig })
AccumulateJobConfig.model_rebuild(_types_namespace={ "InlineJobConfig": InlineJobConfig })
PipelineJobConfig.model_rebuild(_types_namespace={ "InlineJobConfig": InlineJobConfig })
