from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.component import TokenizerComponentConfig, HuggingfaceModelConfig
from mindor.core.logger import logging
from .common import TokenizerTaskService

class HuggingfaceTokenizerTaskService(TokenizerTaskService):
    def __init__(self, id: str, config: TokenizerComponentConfig):
        super().__init__(id, config)

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "transformers" ]

    def _load_tokenizer(self) -> None:
        self._tokenizer = self._load_pretrained_tokenizer()

    def _load_pretrained_tokenizer(self) -> Any:
        tokenizer_cls = self._get_tokenizer_class()
        tokenizer = tokenizer_cls.from_pretrained(self._get_model_path(), **self._get_tokenizer_params())

        if tokenizer.pad_token is None:
            logging.info("Tokenizer does not have a pad_token defined. Configuring pad_token automatically.")
            self._configure_missing_pad_token(tokenizer)

        return tokenizer

    def _configure_missing_pad_token(self, tokenizer: Any) -> None:
        if tokenizer.eos_token is not None:
            tokenizer.pad_token = tokenizer.eos_token
            logging.info(f"Set pad_token to eos_token: {tokenizer.eos_token}")
        else:
            tokenizer.add_special_tokens({ "pad_token": "[PAD]" })
            logging.info("Added new pad_token: [PAD]")

    def _get_tokenizer_class(self) -> Type:
        from transformers import AutoTokenizer
        return AutoTokenizer

    def _get_tokenizer_params(self) -> Dict[str, Any]:
        params: Dict[str, Any] = {}

        if isinstance(self.config.model, HuggingfaceModelConfig):
            if self.config.model.revision:
                params["revision"] = self.config.model.revision

            if self.config.model.cache_dir:
                params["cache_dir"] = self.config.model.cache_dir

            if self.config.model.local_files_only:
                params["local_files_only"] = True

            if self.config.model.token:
                params["token"] = self.config.model.token

        if not self.config.use_fast:
            params["use_fast"] = False

        return params
