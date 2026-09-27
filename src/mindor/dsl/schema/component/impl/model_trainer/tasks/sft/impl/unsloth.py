from typing import Literal, List
from pydantic import Field, model_validator
from mindor.dsl.schema.action import SftModelTrainerActionConfig
from .common import CommonSftModelTrainerComponentConfig
from ...common import ModelTrainerDriverType

class UnslothSftModelTrainerComponentConfig(CommonSftModelTrainerComponentConfig):
    driver: Literal[ModelTrainerDriverType.UNSLOTH]
    # Unsloth applies rope scaling at load time — the value is baked into the
    # model and cannot be changed per action. Set it once at the component level
    # to cover the longest sequence any downstream action will feed in.
    max_seq_length: int = Field(default=4096, description="Maximum sequence length baked into the model at load time via rope scaling.")
    actions: List[SftModelTrainerActionConfig] = Field(default_factory=list, description="Actions this SFT trainer component exposes to workflows.")

    @model_validator(mode="after")
    def validate_unsloth_requires_lora(self):
        # Unsloth's fast kernels only support LoRA/QLoRA fine-tuning; full
        # fine-tuning is not exposed by the FastLanguageModel API.
        if self.lora is None:
            raise ValueError("Unsloth trainer requires 'lora' to be set — full fine-tuning is not supported by the unsloth backend.")
        return self

    @model_validator(mode="after")
    def validate_unsloth_requires_cuda(self):
        # Unsloth ships CUDA-only kernels (triton + bitsandbytes + xformers).
        device = (self.device or "").lower()
        if device not in ("auto", "cuda") and not device.startswith("cuda:"):
            raise ValueError(f"Unsloth trainer requires a CUDA device; got device={self.device!r}. Set 'device' to 'cuda', 'cuda:N', or 'auto'.")
        return self
