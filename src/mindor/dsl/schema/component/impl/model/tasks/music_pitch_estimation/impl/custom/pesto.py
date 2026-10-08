from typing import Literal, List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, model_validator
from mindor.dsl.utils.path import is_local_path
from mindor.dsl.schema.action import PestoMusicPitchEstimationModelActionConfig
from ..common import CommonMusicPitchEstimationModelComponentConfig
from .common import MusicPitchEstimationModelFamily
from ....common import ModelDriverType, ModelConfig, ModelProvider, ModelPrecision

_DEFAULT_MODEL = "mir-1k_g7"
_DEFAULT_STEP_SIZE_MS = 10.0

class PestoBackend(str, Enum):
    TORCH = "torch"
    ONNX  = "onnx"

class PestoStreamingConfig(BaseModel):
    chunk_size: int = Field(..., description="Fixed chunk length in audio samples fed to the model per inference step.")
    max_batch_size: int = Field(default=1, description="Maximum number of concurrent streams the component can serve.")

class PestoMusicPitchEstimationModelComponentConfig(CommonMusicPitchEstimationModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[MusicPitchEstimationModelFamily.PESTO]
    backend: PestoBackend = Field(default=PestoBackend.TORCH, description="Inference backend (torch via pesto-pitch, or onnx via onnxruntime).")
    model: ModelConfig = Field(..., description="PESTO checkpoint — a bundled weight name, local .ckpt path, local .onnx path, or HuggingFace repo.")
    sample_rate: Optional[int] = Field(default=None, description="Sample rate the model expects; required for onnx and for streaming.")
    step_size: Optional[float] = Field(default=None, description="Hop between CQT frames in milliseconds; torch backend only, mutually exclusive with streaming.chunk_size.")
    streaming: Optional[PestoStreamingConfig] = Field(default=None, description="Enable chunked inference; required for onnx backend.")
    providers: Optional[List[str]] = Field(default=None, description="onnxruntime execution providers; auto-selected from device when omitted.")
    actions: List[PestoMusicPitchEstimationModelActionConfig] = Field(default_factory=list, description="Actions this music pitch estimation component exposes to workflows.")

    @classmethod
    def is_supported_precision(cls, precision: ModelPrecision) -> bool:
        # PESTO exposes a float16 toggle on the torch path; onnxruntime bakes
        # dtype into the serialized graph so precision is advisory there.
        return precision in (ModelPrecision.FLOAT32, ModelPrecision.FLOAT16)

    @model_validator(mode="before")
    def inflate_model(cls, values: Dict[str, Any]):
        model = values.get("model") or _DEFAULT_MODEL
        if isinstance(model, str):
            if is_local_path(model) or model.endswith((".ckpt", ".onnx")):
                values["model"] = { "provider": ModelProvider.LOCAL, "path": model }
            else:
                values["model"] = { "provider": ModelProvider.NAMED, "name": model }
        return values

    @model_validator(mode="before")
    def fill_missing_model_provider(cls, values: Dict[str, Any]):
        model = values.get("model")
        if isinstance(model, dict) and "provider" not in model:
            if "repository" in model:
                model["provider"] = ModelProvider.HUGGINGFACE
            elif "path" in model:
                model["provider"] = ModelProvider.LOCAL
            else:
                model["provider"] = ModelProvider.NAMED
        return values

    @model_validator(mode="after")
    def validate_backend_requirements(self):
        if self.backend == PestoBackend.ONNX:
            if self.streaming is None:
                raise ValueError("backend=onnx requires 'streaming' (PESTO ONNX exports are chunked and stateful).")
            if self.sample_rate is None:
                raise ValueError("backend=onnx requires 'sample_rate' (ONNX exports have a fixed sample rate baked into the graph).")
            if self.step_size is not None:
                raise ValueError("'step_size' is torch-only; the ONNX hop is derived from streaming.chunk_size / sample_rate.")

        if self.streaming is not None:
            if self.sample_rate is None:
                raise ValueError("'streaming' requires 'sample_rate'.")
            if self.step_size is not None:
                raise ValueError("'streaming.chunk_size' and 'step_size' are mutually exclusive; pick one.")

        if self.providers is not None and self.backend != PestoBackend.ONNX:
            raise ValueError("'providers' only applies when backend=onnx.")

        return self

    @model_validator(mode="after")
    def apply_default_step_size(self):
        # Offline torch path needs a concrete step_size for pesto.load_model.
        if self.backend == PestoBackend.TORCH and self.streaming is None and self.step_size is None:
            self.step_size = _DEFAULT_STEP_SIZE_MS
        return self
