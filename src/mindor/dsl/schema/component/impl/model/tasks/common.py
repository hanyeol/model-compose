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
    VIDEO_EMBEDDING          = "video-embedding"
    IMAGE_UPSCALE            = "image-upscale"
    IMAGE_BACKGROUND_REMOVAL = "image-background-removal"
    IMAGE_SEGMENTATION       = "image-segmentation"
    TEXT_TO_VIDEO            = "text-to-video"
    IMAGE_TO_VIDEO           = "image-to-video"
    OBJECT_DETECTION         = "object-detection"
    OBJECT_TRACKING          = "object-tracking"
    SHOT_BOUNDARY_DETECTION  = "shot-boundary-detection"
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
    vram: Optional[int] = Field(default=None, description="Estimated VRAM usage in megabytes.")
    ram: Optional[int] = Field(default=None, description="Estimated system RAM usage in megabytes.")

class CommonModelConfig(BaseModel):
    provider: ModelProvider = Field(..., description="Source the model is loaded from.")

class HuggingfaceModelConfig(CommonModelConfig):
    provider: Literal[ModelProvider.HUGGINGFACE]
    repository: str = Field(..., description="HuggingFace Hub repository ID (e.g., meta-llama/Llama-3-8B).")
    filename: Optional[str] = Field(default=None, description="Specific file within the repository to load.")
    revision: Optional[str] = Field(default=None, description="Git revision, tag, or branch of the repository to load.")
    cache_dir: Optional[str] = Field(default=None, description="Local directory where downloaded model files are cached.")
    allow_patterns: Optional[List[str]] = Field(default=None, description="Glob patterns selecting which files to download from the repository snapshot.")
    local_files_only: Union[bool, str] = Field(default=False, description="Whether to skip network access and load only from the local cache.")
    token: Optional[str] = Field(default=None, description="HuggingFace access token used for gated or private repositories.")

    @field_validator("cache_dir", mode="after")
    def expand_cache_dir(cls, value: Optional[str]) -> Optional[str]:
        return os.path.expanduser(value) if value else value

class LocalModelConfig(CommonModelConfig):
    provider: Literal[ModelProvider.LOCAL]
    path: Optional[str] = Field(default=None, description="Local filesystem path to the model file or directory.")
    url: Optional[UrlFetchConfig] = Field(default=None, description="Remote source used to download the model when the local path is missing.")
    bundled: bool = Field(default=False, description="Whether the downloaded file is an archive to extract into `path`.")

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
    name: str = Field(..., description="Pretrained model name known to the selected driver.")

ModelConfig = Annotated[
    Union[
        HuggingfaceModelConfig,
        LocalModelConfig,
        NamedModelConfig,
    ],
    Field(discriminator="provider")
]

class ModelQuantizationConfig(BaseModel):
    type: ModelQuantizationType = Field(..., description="Quantization scheme applied to model weights.")
    compute_dtype: Optional[str] = Field(default=None, description="Compute dtype used with 4-bit quantization (e.g., float16, bfloat16).")
    double_quant: bool = Field(default=True, description="Whether to apply nested quantization for 4-bit weights.")

class PeftAdapterConfig(BaseModel):
    type: PeftAdapterType = Field(..., description="Type of PEFT adapter to load.")
    name: Optional[str] = Field(default=None, description="Name assigned to the adapter for reference.")
    model: ModelConfig = Field(..., description="Adapter model identifier — a HuggingFace repo ID or a local path.")
    weight: Union[float, str] = Field(default=1.0, description="Adapter weight applied when merging with the base model (0.0-1.0).")
    precision: Optional[ModelPrecision] = Field(default=None, description="Numeric precision used for adapter weights and computation.")
    quantization: Optional[Union[str, ModelQuantizationConfig]] = Field(default=None, description="Quantization applied to the adapter weights.")
    low_cpu_mem_usage: Union[bool, str] = Field(default=False, description="Whether to load the adapter with reduced CPU RAM usage.")

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
    priority: OnDemandPriority = Field(default=OnDemandPriority.NORMAL, description="Retention priority when memory pressure forces the model to be unloaded.")
    idle_timeout: Union[str, int, float] = Field(default="300s", description="Idle time before the model is auto-unloaded, as a duration string (e.g., \"5m\") or seconds; \"0s\" disables auto-unload.")

class CommonModelComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.MODEL]
    task: ModelTaskType = Field(..., description="Task the model performs.")
    driver: ModelDriver = Field(..., description="Inference backend used to run the model.")
    model: ModelConfig = Field(..., description="Model identifier — a HuggingFace repo ID or a local path.")
    device_mode: DeviceMode = Field(default=DeviceMode.AUTO, description="Strategy for allocating the model across available devices.")
    device: str = Field(default="auto", description="Compute device the model runs on (e.g., cpu, cuda, cuda:0, mps); \"auto\" selects the best available.")
    runtime_spec: Optional[ModelRuntimeSpec] = Field(default=None, description="Runtime resource hints used for scheduling.")
    precision: Optional[ModelPrecision] = Field(default=None, description="Numeric precision used for model weights and computation.")
    quantization: Optional[Union[str, ModelQuantizationConfig]] = Field(default=None, description="Quantization applied to model weights.")
    low_cpu_mem_usage: Union[bool, str] = Field(default=False, description="Whether to load the model with reduced CPU RAM usage.")
    peft_adapters: Optional[List[PeftAdapterConfig]] = Field(default=None, description="PEFT adapters loaded on top of the base model.")
    preload: bool = Field(default=True, description="Whether to load the model at controller startup.")
    on_demand: Union[bool, OnDemandConfig] = Field(default=False, description="Whether to load and unload the model on demand; accepts a config object for fine-tuning.")

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
    fast_tokenizer: Union[bool, str] = Field(default=True, description="Whether to use the fast Rust-backed tokenizer when available.")
    max_seq_length: int = Field(default=2048, description="Maximum sequence length (in tokens) the model accepts.")
