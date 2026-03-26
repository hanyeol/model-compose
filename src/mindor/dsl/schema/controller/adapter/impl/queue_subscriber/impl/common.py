from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field, model_validator
from ...types import ControllerAdapterType

class QueueSubscriberDriver(str, Enum):
    REDIS = "redis"

class CommonQueueSubscriberControllerAdapterConfig(BaseModel):
    type: Literal[ControllerAdapterType.QUEUE_SUBSCRIBER]
    driver: QueueSubscriberDriver = Field(..., description="Queue backend driver.")
    queue_name: str = Field(default="model-compose:tasks", description="Queue name to consume tasks from.")
    result_prefix: str = Field(default="model-compose:result:", description="Prefix for result keys and pub/sub channels. Result key: {prefix}{run_id}. Pub/sub channel: {prefix}{run_id}.")
    result_ttl: int = Field(default=3600, ge=0, description="TTL in seconds for result entries. 0 means no expiry.")
    max_concurrent: int = Field(default=1, ge=1, description="Maximum number of tasks this worker processes concurrently.")
    worker_id: Optional[str] = Field(default=None, description="Unique identifier for this worker instance. Auto-generated if not set.")
    workflows: List[str] = Field(default=["__default__"], description="List of workflow IDs this worker handles. Each workflow gets its own queue: {queue_name}:{workflow_id}.")

    @model_validator(mode="before")
    def inflate_single_workflow(cls, values: Dict[str, Any]):
        if "workflows" not in values:
            workflow = values.pop("workflow", None)
            if workflow:
                values["workflows"] = [workflow]
        return values
