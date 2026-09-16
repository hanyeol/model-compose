from typing import Literal, List, Optional, Union, Annotated
from enum import Enum
from pydantic import Field, model_validator
from typing import Dict, Any
from mindor.dsl.utils.path import is_local_path
from mindor.dsl.schema.action import AnimateDiffHuggingfaceVideoToVideoModelActionConfig
from .common import CommonVideoToVideoModelComponentConfig
from ...common import ModelDriver, ModelConfig, ModelProvider

class HuggingfaceVideoToVideoModelArchitecture(str, Enum):
    ANIMATEDIFF = "animatediff"

class CommonHuggingfaceVideoToVideoModelComponentConfig(CommonVideoToVideoModelComponentConfig):
    driver: Literal[ModelDriver.HUGGINGFACE]

class AnimateDiffHuggingfaceVideoToVideoModelComponentConfig(CommonHuggingfaceVideoToVideoModelComponentConfig):
    architecture: Literal[HuggingfaceVideoToVideoModelArchitecture.ANIMATEDIFF]
    motion_adapter: ModelConfig = Field(..., description="Motion adapter model applied on top of the base diffusion model.")
    ip_adapter: Optional[ModelConfig] = Field(default=None, description="Optional IP-Adapter used when actions supply a `reference_image`.")
    actions: List[AnimateDiffHuggingfaceVideoToVideoModelActionConfig] = Field(default_factory=list, description="Actions this video-to-video component exposes to workflows.")

    @model_validator(mode="before")
    def inflate_motion_adapter(cls, values: Dict[str, Any]):
        adapter = values.get("motion_adapter")
        if isinstance(adapter, str):
            if is_local_path(adapter):
                values["motion_adapter"] = { "provider": ModelProvider.LOCAL, "path": adapter }
            else:
                values["motion_adapter"] = { "provider": ModelProvider.HUGGINGFACE, "repository": adapter }
        return values

    @model_validator(mode="before")
    def fill_missing_motion_adapter_provider(cls, values: Dict[str, Any]):
        adapter = values.get("motion_adapter")
        if isinstance(adapter, dict) and "provider" not in adapter:
            if "repository" in adapter:
                adapter["provider"] = ModelProvider.HUGGINGFACE
            elif "name" in adapter:
                adapter["provider"] = ModelProvider.NAMED
            else:
                adapter["provider"] = ModelProvider.LOCAL
        return values

    @model_validator(mode="before")
    def inflate_ip_adapter(cls, values: Dict[str, Any]):
        adapter = values.get("ip_adapter")
        if isinstance(adapter, str):
            if is_local_path(adapter):
                values["ip_adapter"] = { "provider": ModelProvider.LOCAL, "path": adapter }
            else:
                values["ip_adapter"] = { "provider": ModelProvider.HUGGINGFACE, "repository": adapter }
        return values

    @model_validator(mode="before")
    def fill_missing_ip_adapter_provider(cls, values: Dict[str, Any]):
        adapter = values.get("ip_adapter")
        if isinstance(adapter, dict) and "provider" not in adapter:
            if "repository" in adapter:
                adapter["provider"] = ModelProvider.HUGGINGFACE
            elif "name" in adapter:
                adapter["provider"] = ModelProvider.NAMED
            else:
                adapter["provider"] = ModelProvider.LOCAL
        return values

HuggingfaceVideoToVideoModelComponentConfig = Annotated[
    Union[
        AnimateDiffHuggingfaceVideoToVideoModelComponentConfig,
    ],
    Field(discriminator="architecture"),
]
