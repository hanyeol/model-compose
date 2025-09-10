from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from mindor.dsl.schema.component import ModelComponentConfig, DeviceMode
from mindor.core.logger import logging
from .common import ModelTaskService

if TYPE_CHECKING:
    from transformers import PreTrainedModel, PreTrainedTokenizer

class UnslothModelTaskService(ModelTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[PreTrainedModel] = None
        self.tokenizer: Optional[PreTrainedTokenizer] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ 
            "unsloth",
            "torch"
        ]

    async def _serve(self) -> None:
        try:
            self.model, self.tokenizer = self._load_pretrained_model()
            logging.info(f"Model and tokenizer loaded successfully: {self.config.model}")
        except Exception as e:
            logging.error(f"Failed to load model '{self.config.model}': {e}")
            raise

    async def _shutdown(self) -> None:
        self.model = None
        self.tokenizer = None
        self.device = None

    def _load_pretrained_model(self) -> Tuple[PreTrainedModel, PreTrainedTokenizer]:
        from unsloth import FastLanguageModel
        
        model = FastLanguageModel.from_pretrained(self.config.model, **self._get_model_params())

        return model

    def _get_model_params(self) -> Dict[str, Any]:
        params: Dict[str, Any] = {}

        if self.config.device_mode != DeviceMode.SINGLE:
            params["device_map"] = self.config.device_mode.value
    
        if self.config.precision is not None:
            params["dtype"] = self.config.precision.value

        return params
