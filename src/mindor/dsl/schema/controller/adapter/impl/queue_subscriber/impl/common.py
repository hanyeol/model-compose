from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field, model_validator
from ...types import ControllerAdapterType

class QueueSubscriberDriver(str, Enum):
    REDIS = "redis"

class CommonQueueSubscriberControllerAdapterConfig(BaseModel):
    type: Literal[ControllerAdapterType.QUEUE_SUBSCRIBER]
    driver: QueueSubscriberDriver = Field(..., description="Queue backend driver.")
    name: str = Field(default="controller-queue", description="Queue name to consume tasks from.")
    result_ttl: str = Field(default="1h", description="TTL for result entries (e.g. '1h', '30m'). '0s' means no expiry.")
    max_concurrent_count: int = Field(default=1, ge=1, description="Max concurrent tasks this worker processes.")
    worker_id: Optional[str] = Field(default=None, description="Unique worker instance ID. Auto-generated if unset.")
    workflows: Optional[List[str]] = Field(default=None, description="Workflow IDs this worker handles.")

    @model_validator(mode="before")
    def inflate_single_workflow(cls, values: Dict[str, Any]):
        if "workflows" not in values:
            workflow = values.pop("workflow", None)
            if workflow:
                values["workflows"] = [workflow]
        return values
