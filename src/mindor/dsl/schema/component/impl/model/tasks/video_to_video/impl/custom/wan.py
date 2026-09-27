from typing import Literal, List, Optional, Dict, Any
from enum import Enum
from pydantic import Field, model_validator
from mindor.dsl.utils.path import is_local_path
from mindor.dsl.schema.action import WanVideoToVideoModelActionConfig
from ..common import CommonVideoToVideoModelComponentConfig
from .common import VideoToVideoModelFamily
from ....common import ModelDriverType, ModelConfig, ModelProvider

class WanVideoToVideoPreset(str, Enum):
    ANIMATE_14B = "animate-14b"

class WanVideoToVideoModelComponentConfig(CommonVideoToVideoModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[VideoToVideoModelFamily.WAN]
    preset: WanVideoToVideoPreset = Field(default=WanVideoToVideoPreset.ANIMATE_14B, description="Wan model preset selecting the checkpoint variant.")
    cpu_offload: bool = Field(default=False, description="Offload submodules to CPU during generation to save VRAM.")
    pose2d_model: ModelConfig = Field(..., description="ViTPose whole-body ONNX checkpoint used to extract driving poses.")
    det_model: ModelConfig = Field(..., description="Person detector ONNX checkpoint (e.g. YOLOv10) used by the pose extractor.")
    sam2_model: Optional[ModelConfig] = Field(default=None, description="SAM2 checkpoint; required only when an action uses `replace_flag`.")
    flux_kontext_model: Optional[ModelConfig] = Field(default=None, description="FLUX.1-Kontext model; required only when an action uses `use_flux` with pose retargeting.")
    actions: List[WanVideoToVideoModelActionConfig] = Field(default_factory=list, description="Actions this video-to-video component exposes to workflows.")

    @model_validator(mode="before")
    def inflate_preprocess_models(cls, values: Dict[str, Any]):
        for name in ("pose2d_model", "det_model", "sam2_model", "flux_kontext_model"):
            value = values.get(name)
            if isinstance(value, str):
                if is_local_path(value):
                    values[name] = { "provider": ModelProvider.LOCAL, "path": value }
                else:
                    values[name] = { "provider": ModelProvider.HUGGINGFACE, "repository": value }
        return values

    @model_validator(mode="before")
    def fill_missing_preprocess_model_provider(cls, values: Dict[str, Any]):
        for name in ("pose2d_model", "det_model", "sam2_model", "flux_kontext_model"):
            value = values.get(name)
            if isinstance(value, dict) and "provider" not in value:
                if "repository" in value:
                    value["provider"] = ModelProvider.HUGGINGFACE
                elif "name" in value:
                    value["provider"] = ModelProvider.NAMED
                else:
                    value["provider"] = ModelProvider.LOCAL
        return values
