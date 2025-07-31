from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator, field_validator
from .common import JobType, CommonJobConfig

class RandomRoutingMode(str, Enum):
    UNIFORM  = "uniform"
    WEIGHTED = "weighted"

class RandomRoutingConfig(BaseModel):
    weight: Optional[float] = Field(default=None, description="")
    target: str = Field(..., description="Destination job ID for this route.")

class RandomRouterJobConfig(CommonJobConfig):
    type: Literal[JobType.RANDOM_ROUTER]
    mode: RandomRoutingMode = Field(default=RandomRoutingMode.UNIFORM, description="")
    routings: List[RandomRoutingConfig] = Field(default_factory=list, description="")

    def get_routing_jobs(self) -> Set[str]:
        return { routing.target for routing in self.routings }
