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

class Quantization(str, Enum):
    NONE = "none"
    FP16 = "fp16"
    BF16 = "bf16"
    INT8 = "int8"
    INT4 = "int4"
    FP4  = "fp4"
    NF4  = "nf4"

class ModelDriver(str, Enum):
    HUGGINGFACE = "huggingface"
    UNSLOTH     = "unsloth"
    VLLM        = "vllm"
    LLAMACPP    = "llamacpp"
    CUSTOM      = "custom"

class ModelProvider(str, Enum):
    HUGGINGFACE = "huggingface"
    LOCAL       = "local"

class ModelFormat(str, Enum):
    PYTORCH     = "pytorch"
    SAFETENSORS = "safetensors" 
    ONNX        = "onnx"
    GGUF        = "gguf"
    TENSORRT    = "tensorrt"

class CommonModelConfig(BaseModel):
    provider: ModelProvider = Field(..., description="Model provider.")

class HuggingfaceModelConfig(CommonModelConfig):
    provider: Literal[ModelProvider.HUGGINGFACE]
    repository: str = Field(..., description="HuggingFace model repository.")
    filename: Optional[str] = Field(default=None, description="Specific file within the repository.")
    revision: Optional[str] = Field(default=None, description="Model version or branch to load.")
    cache_dir: Optional[str] = Field(default=None, description="Directory to cache the model files.")
    local_files_only: bool = Field(default=False, description="Force loading from local files only.")
    token: Optional[str] = Field(default=None, description="HuggingFace access token for private models.")

class LocalModelConfig(CommonModelConfig):
    provider: Literal[ModelProvider.LOCAL]
    path: str = Field(..., description="Model path.")
    format: ModelFormat = Field(default=ModelFormat.PYTORCH, description="Model file format.")

ModelConfig = Annotated[
    Union[ 
        HuggingfaceModelConfig,
        LocalModelConfig,
    ],
    Field(discriminator="provider")
]

class CommonModelComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.MODEL]
    task: ModelTaskType = Field(..., description="Type of task the model performs.")
    driver: ModelDriver = Field(default=ModelDriver.HUGGINGFACE, description="Model inference framework driver to use.")
    model: Union[str, ModelConfig] = Field(..., description="Model source configuration.")
    device_mode: DeviceMode = Field(default=DeviceMode.AUTO, description="Device allocation mode.")
    device: str = Field(default="cpu", description="Computation device to use.")
    precision: Optional[ModelPrecision] = Field(default=None, description="Numerical precision to use when loading the model weights.")
    quantization: Quantization = Field(default=Quantization.NONE, description="Quantization method.")
    low_cpu_mem_usage: bool = Field(default=False, description="Load model with minimal CPU RAM usage.")
    fast_tokenizer: bool = Field(default=True, description="Whether to use the fast tokenizer if available.")
    max_seq_length: int = Field(default=2048, description="")

    @model_validator(mode="before")
    def fill_missing_model_provider(cls, values: Dict[str, Any]):
        model = values.get("model")
        if isinstance(model, dict) and "provider" not in model:
            model["provider"] = ModelProvider.HUGGINGFACE
        return values

class ClassificationModelComponentConfig(CommonModelComponentConfig):
    labels: Optional[List[str]] = Field(default=None, description="List of class labels for classification tasks.")
