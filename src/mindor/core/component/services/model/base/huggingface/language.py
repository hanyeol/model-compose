from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Optional, Dict, List, Any
from mindor.dsl.schema.component import ModelComponentConfig
from mindor.core.logger import logging
from .base import HuggingfaceModelTaskService

if TYPE_CHECKING:
    from transformers import PreTrainedModel, PreTrainedTokenizer
    import torch

class HuggingfaceLanguageModelTaskService(HuggingfaceModelTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[PreTrainedModel] = None
        self.tokenizer: Optional[PreTrainedTokenizer] = None
        self.device: Optional[torch.device] = None

    def _get_setup_requirements(self) -> List[str]:
        return [
            *super()._get_setup_requirements(),
            "peft>=0.5.0",
            "sentencepiece",
        ]

    async def _load_model(self) -> None:
        self.model, model_path = await self._load_pretrained_model()
        self.tokenizer = await self._load_pretrained_tokenizer(model_path)
        self.device = self._get_model_device(self.model)

    async def _unload_model(self) -> None:
        self.model = None
        self.tokenizer = None
        self.device = None

    async def _load_pretrained_tokenizer(self, model_path: str) -> Optional[PreTrainedTokenizer]:
        tokenizer_cls = self._get_tokenizer_class()

        if not tokenizer_cls:
            return None

        tokenizer = await self._run_in_executor(
            tokenizer_cls.from_pretrained,
            model_path,
            **self._get_tokenizer_params()
        )

        if tokenizer.pad_token is None:
            logging.info("Tokenizer does not have a pad_token defined. Configuring pad_token automatically.")
            self._configure_missing_pad_token(tokenizer)

        return tokenizer

    def _configure_missing_pad_token(self, tokenizer: PreTrainedTokenizer) -> None:
        if tokenizer.eos_token is not None:
            tokenizer.pad_token = tokenizer.eos_token
            logging.debug(f"Set pad_token to eos_token: {tokenizer.eos_token}")
        else:
            tokenizer.add_special_tokens({ "pad_token": "[PAD]" })
            logging.debug("Added new pad_token: [PAD]")

    def _get_tokenizer_class(self) -> Optional[Type[PreTrainedTokenizer]]:
        raise NotImplementedError("Tokenizer class loader not implemented.")

    def _get_tokenizer_params(self) -> Dict[str, Any]:
        params = self._get_model_params(self.config.model)

        if not self.config.fast_tokenizer:
            params["use_fast"] = False

        return params
