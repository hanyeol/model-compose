from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator
from ...common import CommonComponentConfig, ComponentType
from .types import ModelTaskType

class DeviceMode(str, Enum):
    SINGLE = "single"
    AUTO   = "auto"

class ModelPrecision(str, Enum):
    AUTO     = "auto"
    FLOAT32  = "float32"
    FLOAT16  = "float16"
    BFLOAT16 = "bfloat16"

class AttentionMode(str, Enum):
    SDPA              = "sdpa"
    EAGER             = "eager"
    FLASH_ATTENTION_2 = "flash_attention_2"
    MEM_EFFICIENT     = "mem_efficient"

class ModelSourceConfig(BaseModel):
    model_id: str = Field(..., description="Model identifier.")
    provider: Optional[str] = Field(default=None, description="Model provider.")
    revision: Optional[str] = Field(default=None, description="Model version or branch to load.")
    filename: Optional[str] = Field(default=None, description="Specific file inside the model repo.")

class CommonModelComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.MODEL]
    task: ModelTaskType = Field(..., description="Type of task the model performs.")
    model: Union[str, ModelSourceConfig] = Field(..., description="Model source.")
    cache_dir: Optional[str] = Field(default=None, description="Directory to cache the model files.")
    local_files_only: bool = Field(default=False, description="Force loading from local files only.")
    device_mode: DeviceMode = Field(default=DeviceMode.AUTO, description="Device allocation mode.")
    device: str = Field(default="cpu", description="Computation device to use.")
    precision: Optional[ModelPrecision] = Field(default=None, description="Numerical precision to use when loading the model weights.")
    low_cpu_mem_usage: bool = Field(default=False, description="Load model with minimal CPU RAM usage.")
    fast_tokenizer: bool = Field(default=True, description="Whether to use the fast tokenizer if available.")

class ClassificationModelComponentConfig(CommonModelComponentConfig):
    labels: Optional[List[str]] = Field(default=None, description="List of class labels for classification tasks.")
