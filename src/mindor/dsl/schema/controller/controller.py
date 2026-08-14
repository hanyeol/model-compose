from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator, field_validator
from mindor.dsl.schema.runtime import RuntimeConfig, RuntimeType
from .adapter import ControllerAdapterConfig
from .queue import ControllerQueueConfig, ControllerQueueDriver, RedisControllerQueueConfig
from .webui import ControllerWebUIConfig, ControllerWebUIDriver

class ControllerConfig(BaseModel):
    name: Optional[str] = Field(default=None, description="Name of controller.")
    runtime: RuntimeConfig = Field(..., description="Runtime environment in which the controller executes.")
    max_concurrent_count: int = Field(default=0, description="Maximum concurrent tasks the controller runs; 0 means unbounded.")
    shutdown_pending_period: Union[str, int, float] = Field(default="0s", description="Grace period before shutdown begins, allowing traffic to drain.")
    shutdown_timeout: Union[str, int, float] = Field(default="30s", description="Maximum time to wait for in-progress tasks during shutdown.")
    threaded: bool = Field(default=False, description="Whether to run tasks on separate worker threads.")
    queue: Optional[ControllerQueueConfig] = Field(default=None, description="Queue used to dispatch workflow execution to remote workers.")
    webui: Optional[ControllerWebUIConfig] = Field(default=None, description="Web UI served alongside the controller.")
    adapters: List[ControllerAdapterConfig] = Field(default_factory=list, description="Protocol adapters that expose the controller to clients.")

    @model_validator(mode="before")
    def inflate_single_adapter(cls, values: Dict[str, Any]):
        if "adapters" not in values:
            adapter_values = values.pop("adapter", None)
            if adapter_values:
                values["adapters"] = [ adapter_values ]
        return values

    @model_validator(mode="before")
    def inflate_runtime(cls, values: Dict[str, Any]):
        runtime = values.get("runtime")
        if runtime is None or isinstance(runtime, str):
            values["runtime"] = { "type": runtime or RuntimeType.NATIVE }
        return values

    @model_validator(mode="before")
    def fill_missing_webui_driver(cls, values: Dict[str, Any]):
        webui = values.get("webui")
        if isinstance(webui, dict) and "driver" not in webui:
            webui["driver"] = ControllerWebUIDriver.GRADIO
        return values

    @model_validator(mode="after")
    def validate_runtime(self):
        if self.runtime.type in [ RuntimeType.VIRTUALENV ]:
            raise ValueError(f"runtime type '{self.runtime.type.value}' is not allowed for controller.")
        return self
