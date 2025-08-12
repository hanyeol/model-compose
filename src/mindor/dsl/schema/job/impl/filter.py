from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator, field_validator
from mindor.dsl.schema.component import ComponentConfig
from .common import JobType, OutputJobConfig

class FilterJobConfig(OutputJobConfig):
    type: Literal[JobType.FILTER]
