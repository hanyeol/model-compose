from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator
from mindor.dsl.utils.path import is_local_path
from ...common import CommonComponentConfig, ComponentType

class ModelTaskType(str, Enum):
    TEXT_GENERATION     = "text-generation"
    CHAT_COMPLETION     = "chat-completion"
    TEXT_CLASSIFICATION = "text-classification" 
    TEXT_EMBEDDING      = "text-embedding"
    IMAGE_TO_TEXT       = "image-to-text"
    IMAGE_GENERATION    = "image-generation"
    IMAGE_UPSCALE       = "image-upscale"
    FACE_EMBEDDING      = "face-embedding"

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

class ModelPrecision(str, Enum):
    AUTO     = "auto"
    FLOAT32  = "float32"
    FLOAT16  = "float16"
    BFLOAT16 = "bfloat16"

class ModelQuantization(str, Enum):
    NONE = "none"
    FP16 = "fp16"
    BF16 = "bf16"
    INT8 = "int8"
    INT4 = "int4"
    FP4  = "fp4"
    NF4  = "nf4"

class DeviceMode(str, Enum):
    SINGLE = "single"
    AUTO   = "auto"

class CommonModelConfig(BaseModel):
    provider: ModelProvider = Field(..., description="Model provider.")

class HuggingfaceModelConfig(CommonModelConfig):
    provider: Literal[ModelProvider.HUGGINGFACE]
    repository: str = Field(..., description="HuggingFace model repository.")
    filename: Optional[str] = Field(default=None, description="Specific file within the repository.")
    revision: Optional[str] = Field(default=None, description="Model version or branch to load.")
    cache_dir: Optional[str] = Field(default=None, description="Directory to cache the model files.")
    local_files_only: Union[bool, str] = Field(default=False, description="Force loading from local files only.")
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

class PeftAdapterType(str, Enum):
    LORA = "lora"

class PeftAdapterConfig(BaseModel):
    type: PeftAdapterType = Field(..., description="Type of the adapter.")
    name: Optional[str] = Field(default=None, description="Name for the adapter.")
    model: Union[str, ModelConfig] = Field(..., description="Model source configuration.")
    weight: Union[float, str] = Field(default=1.0, description="Adapter weight/scale (0.0-1.0).")
    precision: Optional[ModelPrecision] = Field(default=None, description="Numerical precision to use when loading the model weights.")
    quantization: ModelQuantization = Field(default=ModelQuantization.NONE, description="Quantization method.")
    low_cpu_mem_usage: Union[bool, str] = Field(default=False, description="Load model with minimal CPU RAM usage.")

    @model_validator(mode="before")
    def inflate_model(cls, values: Dict[str, Any]):
        model = values.get("model")
        if isinstance(model, str):
            if is_local_path(model):
                values["model"] = { "provider": ModelProvider.LOCAL, "path": model }
            else:
                values["model"] = { "provider": ModelProvider.HUGGINGFACE, "repository": model }
        return values

    @model_validator(mode="before")
    def fill_missing_model_provider(cls, values: Dict[str, Any]):
        model = values.get("model")
        if isinstance(model, dict) and "provider" not in model:
            model["provider"] = ModelProvider.HUGGINGFACE
        return values

class CommonModelComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.MODEL]
    task: ModelTaskType = Field(..., description="Type of task the model performs.")
    driver: ModelDriver = Field(default=ModelDriver.HUGGINGFACE, description="Model inference framework driver to use.")
    model: Union[str, ModelConfig] = Field(..., description="Model source configuration.")
    device_mode: DeviceMode = Field(default=DeviceMode.AUTO, description="Device allocation mode.")
    device: str = Field(default="cpu", description="Computation device to use.")
    precision: Optional[ModelPrecision] = Field(default=None, description="Numerical precision to use when loading the model weights.")
    quantization: ModelQuantization = Field(default=ModelQuantization.NONE, description="Quantization method.")
    low_cpu_mem_usage: Union[bool, str] = Field(default=False, description="Load model with minimal CPU RAM usage.")
    peft_adapters: Optional[List[PeftAdapterConfig]] = Field(default=None, description="PEFT adapters to load on top of the base model.")

    @model_validator(mode="before")
    def inflate_model(cls, values: Dict[str, Any]):
        model = values.get("model")
        if isinstance(model, str):
            if is_local_path(model):
                values["model"] = { "provider": ModelProvider.LOCAL, "path": model }
            else:
                values["model"] = { "provider": ModelProvider.HUGGINGFACE, "repository": model }
        return values

    @model_validator(mode="before")
    def fill_missing_model_provider(cls, values: Dict[str, Any]):
        model = values.get("model")
        if isinstance(model, dict) and "provider" not in model:
            model["provider"] = ModelProvider.HUGGINGFACE
        return values

class LanguageModelComponentConfig(CommonModelComponentConfig):
    fast_tokenizer: Union[bool, str] = Field(default=True, description="Whether to use the fast tokenizer if available.")
    max_seq_length: int = Field(default=2048, description="Maximum sequence length for the model.")
