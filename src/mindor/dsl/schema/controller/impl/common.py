from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator, field_validator
from mindor.dsl.schema.runtime import RuntimeConfig, RuntimeType
from .types import ControllerType
from ..webui import ControllerWebUIConfig, ControllerWebUIDriver

class CommonControllerConfig(BaseModel):
    name: Optional[str] = Field(default=None, description="Name used to identify this controller.")
    type: ControllerType = Field(..., description="Type of controller to run.")
    runtime: RuntimeConfig = Field(..., description="Runtime environment settings.")
    max_concurrent_count: int = Field(default=1, description="Maximum number of tasks that can be executed concurrently.")
    threaded: bool = Field(default=False, description="Whether to run tasks in separate threads.")
    webui: Optional[ControllerWebUIConfig] = Field(default=None, description="Configuration for the controller's Web UI interface.")

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
