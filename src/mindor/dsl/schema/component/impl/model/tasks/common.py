from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import field_validator, model_validator
from mindor.dsl.utils.path import is_local_path
from mindor.dsl.schema.common.url import UrlFetchConfig
from ...common import CommonComponentConfig, ComponentType
import os

class ModelTaskType(str, Enum):
    TEXT_GENERATION          = "text-generation"
    CHAT_COMPLETION          = "chat-completion"
    TEXT_TO_TEXT             = "text-to-text"
    TEXT_CLASSIFICATION      = "text-classification"
    TEXT_EMBEDDING           = "text-embedding"
    TEXT_RERANKING           = "text-reranking"
    IMAGE_TO_TEXT            = "image-to-text"
    IMAGE_TEXT_TO_TEXT       = "image-text-to-text"
    IMAGE_GENERATION         = "image-generation"
    IMAGE_EMBEDDING          = "image-embedding"
    IMAGE_UPSCALE            = "image-upscale"
    IMAGE_BACKGROUND_REMOVAL = "image-background-removal"
    IMAGE_SEGMENTATION       = "image-segmentation"
    OBJECT_DETECTION         = "object-detection"
    FACE_DETECTION           = "face-detection"
    FACE_EMBEDDING           = "face-embedding"
    FACE_TRACKING            = "face-tracking"
    FACE_SWAP                = "face-swap"
    POSE_DETECTION           = "pose-detection"
    POSE_TRACKING            = "pose-tracking"
    TEXT_TO_SPEECH           = "text-to-speech"
    SPEECH_TO_TEXT           = "speech-to-text"
    AUDIO_TEXT_ALIGNMENT     = "audio-text-alignment"
    VOICE_ACTIVITY_DETECTION = "voice-activity-detection"
    SPEAKER_DIARIZATION      = "speaker-diarization"
    MUSIC_GENERATION         = "music-generation"
    MUSIC_SOURCE_SEPARATION  = "music-source-separation"

class ModelDriver(str, Enum):
    HUGGINGFACE = "huggingface"
    UNSLOTH     = "unsloth"
    VLLM        = "vllm"
    LLAMACPP    = "llamacpp"
    CUSTOM      = "custom"

class ModelProvider(str, Enum):
    HUGGINGFACE = "huggingface"
    LOCAL       = "local"
    NAMED       = "named"

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

class ModelQuantizationType(str, Enum):
    INT8 = "int8"
    INT4 = "int4"
    FP4  = "fp4"
    NF4  = "nf4"

class PeftAdapterType(str, Enum):
    LORA = "lora"

class DeviceMode(str, Enum):
    SINGLE = "single"
    AUTO   = "auto"

class OnDemandPriority(str, Enum):
    HIGH   = "high"
    NORMAL = "normal"
    LOW    = "low"

class ModelRuntimeSpec(BaseModel):
    vram: Optional[int] = Field(default=None, description="Estimated VRAM usage in MB.")
    ram: Optional[int] = Field(default=None, description="Estimated system RAM usage in MB.")

class CommonModelConfig(BaseModel):
    provider: ModelProvider = Field(..., description="Model provider.")

class HuggingfaceModelConfig(CommonModelConfig):
    provider: Literal[ModelProvider.HUGGINGFACE]
    repository: str = Field(..., description="HuggingFace model repository.")
    filename: Optional[str] = Field(default=None, description="Specific file within the repository.")
    revision: Optional[str] = Field(default=None, description="Model version or branch to load.")
    cache_dir: Optional[str] = Field(default=None, description="Directory to cache the model files.")
    allow_patterns: Optional[List[str]] = Field(default=None, description="Glob patterns for which files to include when downloading the snapshot from HuggingFace Hub.")
    local_files_only: Union[bool, str] = Field(default=False, description="Force loading from local files only.")
    token: Optional[str] = Field(default=None, description="HuggingFace access token for private models.")

    @field_validator("cache_dir", mode="after")
    def expand_cache_dir(cls, value: Optional[str]) -> Optional[str]:
        return os.path.expanduser(value) if value else value

class LocalModelConfig(CommonModelConfig):
    provider: Literal[ModelProvider.LOCAL]
    path: Optional[str] = Field(default=None, description="Local path to the model file or directory.")
    url: Optional[UrlFetchConfig] = Field(default=None, description="Fetch config used when the local path is missing.")
    bundled: bool = Field(default=False, description="Whether the downloaded file is an archive to extract into 'path'.")

    @field_validator("path", mode="after")
    def expand_path(cls, value: Optional[str]) -> Optional[str]:
        return os.path.expanduser(value) if value else value

    @model_validator(mode="before")
    def inflate_url(cls, values: Dict[str, Any]):
        url = values.get("url")
        if isinstance(url, str):
            values["url"] = { "endpoint": url }
        return values

    @model_validator(mode="after")
    def apply_default_path(self):
        if not self.path and self.url:
            filename = os.path.basename(self.url.endpoint)
            # For bundled archives the on-disk path names the extracted
            # directory, not the archive — strip the archive suffix so the
            # directory name is clean (e.g. `antelopev2.zip` -> `antelopev2`).
            if self.bundled:
                for suffix in (".tar.gz", ".tgz", ".tar", ".zip"):
                    if filename.lower().endswith(suffix):
                        filename = filename[: -len(suffix)]
                        break
            subdir = self._cache_subdir()
            if subdir:
                self.path = os.path.join(self.get_cache_dir(), subdir, filename)
            else:
                self.path = os.path.join(self.get_cache_dir(), filename)
        return self

    @model_validator(mode="after")
    def validate_path_or_url(self):
        if not self.path and not self.url:
            raise ValueError("LocalModelConfig requires 'path' or 'url'.")
        return self

    def get_cache_dir(self) -> str:
        return os.path.join(os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")), "models")

    def _cache_subdir(self) -> Optional[str]:
        return None

class NamedModelConfig(CommonModelConfig):
    provider: Literal[ModelProvider.NAMED]
    name: str = Field(..., description="Driver-provided pretrained model name.")

ModelConfig = Annotated[
    Union[
        HuggingfaceModelConfig,
        LocalModelConfig,
        NamedModelConfig,
    ],
    Field(discriminator="provider")
]

class ModelQuantizationConfig(BaseModel):
    type: ModelQuantizationType = Field(..., description="Quantization type.")
    compute_dtype: Optional[str] = Field(default=None, description="Compute dtype for 4-bit quantization (e.g., 'float16', 'bfloat16').")
    double_quant: bool = Field(default=True, description="Use nested quantization for 4-bit.")

class PeftAdapterConfig(BaseModel):
    type: PeftAdapterType = Field(..., description="Type of the adapter.")
    name: Optional[str] = Field(default=None, description="Name for the adapter.")
    model: ModelConfig = Field(..., description="Model repository or local file path.")
    weight: Union[float, str] = Field(default=1.0, description="Adapter weight/scale (0.0-1.0).")
    precision: Optional[ModelPrecision] = Field(default=None, description="Numerical precision to use when loading the model weights.")
    quantization: Optional[Union[str, ModelQuantizationConfig]] = Field(default=None, description="Quantization configuration.")
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
            if "repository" in model:
                model["provider"] = ModelProvider.HUGGINGFACE
            elif "name" in model:
                model["provider"] = ModelProvider.NAMED
            else:
                model["provider"] = ModelProvider.LOCAL
        return values

    @model_validator(mode="before")
    def inflate_quantization(cls, values: Dict[str, Any]):
        quantization = values.get("quantization")
        if isinstance(quantization, str):
            values["quantization"] = { "type": quantization }
        return values

class OnDemandConfig(BaseModel):
    priority: OnDemandPriority = Field(default=OnDemandPriority.NORMAL, description="Memory retention priority when memory pressure requires unloading.")
    idle_timeout: Union[str, int, float] = Field(default="300s", description="Idle time before auto-unloading (e.g. '5m', '300s'). '0s' disables auto-unload.")

class CommonModelComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.MODEL]
    task: ModelTaskType = Field(..., description="Type of task the model performs.")
    driver: ModelDriver = Field(..., description="Model inference framework driver to use.")
    model: ModelConfig = Field(..., description="Model repository or local file path.")
    device_mode: DeviceMode = Field(default=DeviceMode.AUTO, description="Device allocation mode.")
    device: str = Field(default="auto", description="Computation device to use ('auto' picks cuda > mps > cpu; ignored when device_mode is 'auto').")
    runtime_spec: Optional[ModelRuntimeSpec] = Field(default=None, description="Runtime specification hints for the model.")
    precision: Optional[ModelPrecision] = Field(default=None, description="Numerical precision to use when loading the model weights.")
    quantization: Optional[Union[str, ModelQuantizationConfig]] = Field(default=None, description="Quantization configuration.")
    low_cpu_mem_usage: Union[bool, str] = Field(default=False, description="Load model with minimal CPU RAM usage.")
    peft_adapters: Optional[List[PeftAdapterConfig]] = Field(default=None, description="PEFT adapters to load on top of the base model.")
    preload: bool = Field(default=True, description="Whether to load the model at startup.")
    on_demand: Union[bool, OnDemandConfig] = Field(default=False, description="Enable on-demand loading/unloading. True uses default settings.")

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
            if "repository" in model:
                model["provider"] = ModelProvider.HUGGINGFACE
            elif "name" in model:
                model["provider"] = ModelProvider.NAMED
            else:
                model["provider"] = ModelProvider.LOCAL
        return values

    @model_validator(mode="before")
    def inflate_on_demand(cls, values: Dict[str, Any]):
        on_demand = values.get("on_demand")
        if on_demand is True:
            values["on_demand"] = {}
        return values

    @model_validator(mode="before")
    def inflate_quantization(cls, values: Dict[str, Any]):
        quantization = values.get("quantization")
        if isinstance(quantization, str):
            values["quantization"] = { "type": quantization }
        return values

class LanguageModelComponentConfig(CommonModelComponentConfig):
    fast_tokenizer: Union[bool, str] = Field(default=True, description="Whether to use the fast tokenizer if available.")
    max_seq_length: int = Field(default=2048, description="Maximum sequence length for the model.")
