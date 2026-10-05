from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator, field_validator
from .common import JobType, CommonJobConfig

class RandomRoutingMode(str, Enum):
    UNIFORM  = "uniform"
    WEIGHTED = "weighted"

class RandomRoutingConfig(BaseModel):
    weight: Optional[float] = Field(default=None, description="Relative selection weight used in weighted random routing.")
    to: str = Field(..., description="ID of the destination job for this route.")

class RandomRouterJobConfig(CommonJobConfig):
    type: Literal[JobType.RANDOM_ROUTER]
    mode: RandomRoutingMode = Field(default=RandomRoutingMode.UNIFORM, description="Selection strategy used to pick a route (e.g., uniform, weighted).")
    session: Optional[str] = Field(default=None, description="Rendered expression that makes routing sticky for the same value (e.g., `${context.session_id}`); falls back to random when empty.")
    salt: Optional[str] = Field(default=None, description="Optional salt isolating this router's hashing from others; defaults to `{workflow_id}:{job_id}`.")
    routings: List[RandomRoutingConfig] = Field(default_factory=list, description="Candidate routes the router chooses from.")

    def get_routing_jobs(self) -> Set[str]:
        jobs = super().get_routing_jobs()
        jobs.update(routing.to for routing in self.routings)
        return jobs
