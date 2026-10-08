from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import CosyvoiceTextToSpeechModelActionConfig
from ..common import CommonTextToSpeechModelComponentConfig
from .common import TextToSpeechModelFamily
from ....common import ModelDriverType, ModelPrecision

class CosyvoiceTextToSpeechModelComponentConfig(CommonTextToSpeechModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[TextToSpeechModelFamily.COSYVOICE]
    load_jit: bool = Field(default=False, description="Whether to load JIT-compiled modules; supported only on CUDA.")
    load_trt: bool = Field(default=False, description="Whether to load TensorRT engines; supported only on CUDA.")
    load_vllm: bool = Field(default=False, description="Whether to load the vLLM runtime for the LLM stage; CosyVoice2/3 on CUDA only.")
    actions: List[CosyvoiceTextToSpeechModelActionConfig] = Field(default_factory=list, description="Actions this text-to-speech component exposes to workflows.")

    @classmethod
    def is_supported_precision(cls, precision: ModelPrecision) -> bool:
        # Upstream only exposes a float16 toggle (CUDA-only); the rest aren't wired through.
        return precision in (ModelPrecision.FLOAT32, ModelPrecision.FLOAT16)
