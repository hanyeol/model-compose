from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import CosyvoiceTextToSpeechModelActionConfig
from ...common import CommonTextToSpeechModelComponentConfig
from .common import TextToSpeechModelFamily
from .....common import ModelDriver

class CosyvoiceTextToSpeechModelComponentConfig(CommonTextToSpeechModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[TextToSpeechModelFamily.COSYVOICE]
    actions: List[CosyvoiceTextToSpeechModelActionConfig] = Field(default_factory=list)
    load_jit: bool = Field(default=False, description="Load JIT-compiled modules (CUDA only).")
    load_trt: bool = Field(default=False, description="Load TensorRT engines (CUDA only).")
    load_vllm: bool = Field(default=False, description="Load vLLM runtime for the LLM stage (CosyVoice2/3 only, CUDA only).")
    fp16: bool = Field(default=False, description="Run inference in fp16 (CUDA only).")
