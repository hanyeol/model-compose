from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from pydantic import BaseModel
from mindor.dsl.schema.component import ModelComponentConfig, ModelConfig, DeviceMode
from .common import ModelTaskService

if TYPE_CHECKING:
    from transformers import PreTrainedModel, PreTrainedTokenizer

class UnslothModelTaskService(ModelTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[PreTrainedModel] = None
        self.tokenizer: Optional[PreTrainedTokenizer] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "unsloth", "transformers", "torch" ]

    async def _load_model(self) -> None:
        self.model, self.tokenizer = await self._load_pretrained_model()

    async def _unload_model(self) -> None:
        self.model = None
        self.tokenizer = None

    async def _load_pretrained_model(self) -> Tuple[PreTrainedModel, PreTrainedTokenizer]:
        from unsloth import FastLanguageModel

        model_path = await self._provision_model(self.config.model)
        params = self._get_model_params(self.config.model)
        options = self._get_model_options(self.config)

        if options:
            params.update(options)

        model = FastLanguageModel.from_pretrained(model_path, **params)

        return model

    def _get_model_params(self, model: ModelConfig) -> Dict[str, Any]:
        return {}

    def _get_model_options(self, config: BaseModel) -> Dict[str, Any]:
        options: Dict[str, Any] = {}

        if self.config.device_mode != DeviceMode.SINGLE:
            options["device_map"] = self.config.device_mode.value

        precision = getattr(config, "precision", None)

        if precision is not None:
            options["dtype"] = precision.value

        return options
