from __future__ import annotations

from typing import List
from mindor.core.foundation.package.torch import torch_requirements
from .common import ModelTrainerTaskDriver

class UnslothModelTrainerTaskDriver(ModelTrainerTaskDriver):
    def _get_setup_requirements(self) -> List[str]:
        # Unsloth bundles transformers/peft/trl/bitsandbytes/xformers/triton as
        # runtime dependencies at compatible pinned versions, so we deliberately
        # don't pin them separately here — letting unsloth pick its known-good
        # combination avoids cross-package conflicts.
        return [
            *self._get_torch_requirements(),
            *self._get_unsloth_requirements(),
            *self._get_huggingface_hub_requirements(),
        ]

    def _get_torch_requirements(self) -> List[str]:
        return torch_requirements("torch")

    def _get_unsloth_requirements(self) -> List[str]:
        return [ "unsloth" ]

    def _get_huggingface_hub_requirements(self) -> List[str]:
        return [ "huggingface_hub<2.0" ]
