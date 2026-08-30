from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import Field
from .component import ComponentJobConfig
from .for_each import ForEachJobConfig
from .accumulate import AccumulateJobConfig
from .pipeline import PipelineJobConfig

InlineJobConfig = Annotated[
    Union[
        ComponentJobConfig,
        ForEachJobConfig,
        AccumulateJobConfig,
        PipelineJobConfig,
    ],
    Field(discriminator="type"),
]

# The three configs above reference `InlineJobConfig` as a forward string;
# rebuild them here so pydantic resolves that reference against the union just defined.
ForEachJobConfig.model_rebuild(_types_namespace={ "InlineJobConfig": InlineJobConfig })
AccumulateJobConfig.model_rebuild(_types_namespace={ "InlineJobConfig": InlineJobConfig })
PipelineJobConfig.model_rebuild(_types_namespace={ "InlineJobConfig": InlineJobConfig })
