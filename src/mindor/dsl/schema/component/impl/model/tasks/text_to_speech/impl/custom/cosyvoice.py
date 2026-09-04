from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import CosyvoiceTextToSpeechModelActionConfig
from ..common import CommonTextToSpeechModelComponentConfig
from .common import TextToSpeechModelFamily
from ....common import ModelDriver

class CosyvoiceTextToSpeechModelComponentConfig(CommonTextToSpeechModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[TextToSpeechModelFamily.COSYVOICE]
    actions: List[CosyvoiceTextToSpeechModelActionConfig] = Field(default_factory=list, description="Actions this text-to-speech component exposes to workflows.")
    load_jit: bool = Field(default=False, description="Whether to load JIT-compiled modules; supported only on CUDA.")
    load_trt: bool = Field(default=False, description="Whether to load TensorRT engines; supported only on CUDA.")
    load_vllm: bool = Field(default=False, description="Whether to load the vLLM runtime for the LLM stage; CosyVoice2/3 on CUDA only.")
    fp16: bool = Field(default=False, description="Whether to run inference in fp16 precision; supported only on CUDA.")
