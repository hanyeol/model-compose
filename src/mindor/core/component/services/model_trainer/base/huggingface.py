from __future__ import annotations
from typing import TYPE_CHECKING

from typing import List
from mindor.core.foundation.package.torch import torch_requirements
from .common import ModelTrainerTaskDriver

class HuggingfaceModelTrainerTaskDriver(ModelTrainerTaskDriver):
    def _get_setup_requirements(self) -> List[str]:
        requirements = [
            *self._get_torch_requirements(),
            *self._get_transformers_requirements(),
            *self._get_datasets_requirements(),
            *self._get_huggingface_hub_requirements(),
            "accelerate",
        ]

        # quantization implies lora in this scope (see validate_quantization_requires_lora);
        # bitsandbytes needs its own kernel package on top of the peft adapter machinery.
        if self.config.lora is not None:
            requirements.extend(self._get_peft_requirements())

        if self.config.quantization is not None:
            requirements.extend(self._get_bitsandbytes_requirements())

        return requirements

    def _get_torch_requirements(self) -> List[str]:
        return torch_requirements("torch")

    def _get_transformers_requirements(self) -> List[str]:
        return [ "transformers>=4.52.0" ]

    def _get_datasets_requirements(self) -> List[str]:
        # Pin below datasets 4.0 — TRL 0.13's conversational auto-detection
        # compares Feature objects that changed representation in datasets 4.0,
        # so a rewritten `messages` column is no longer recognized as
        # conversational data and SFTTrainer falls back to raw text encoding.
        return [ "datasets>=2.14,<4.0" ]

    def _get_huggingface_hub_requirements(self) -> List[str]:
        return [ "huggingface_hub<2.0" ]

    def _get_peft_requirements(self) -> List[str]:
        return [ "peft" ]

    def _get_bitsandbytes_requirements(self) -> List[str]:
        return [ "bitsandbytes>=0.50.0" ]
