from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Tuple, Type, Literal, Optional, Dict, List, Set, Annotated, Callable, Any
from pydantic import BaseModel
from mindor.dsl.schema.component import ModelComponentConfig, ModelConfig, HuggingfaceModelConfig, ModelQuantizationType
from mindor.dsl.schema.component.impl.model.tasks.base.sglang import SglangEngineOptionsConfig
from mindor.core.logger import logging
from .common import ModelTaskDriver

if TYPE_CHECKING:
    from sglang import Engine
    from transformers.tokenization_utils_base import PreTrainedTokenizerBase

_BITSANDBYTES_QUANT_TYPES = {
    ModelQuantizationType.INT8,
    ModelQuantizationType.INT4,
    ModelQuantizationType.FP4,
    ModelQuantizationType.NF4,
}

class SglangModelTaskDriver(ModelTaskDriver):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.engine: Optional[Engine] = None
        self.tokenizer: Optional[PreTrainedTokenizerBase] = None

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        return [ "sglang" ]

    async def _load_model(self) -> None:
        from sglang import Engine
        from transformers import AutoTokenizer

        model_path = await self._provision_model(self.config.model)

        logging.info(f"Component '{self.id}': loading SGLang model from '{model_path}'")

        def _load() -> Engine:
            params: Dict[str, Any] = {
                **self._get_model_params(self.config.model),
                **self._get_model_options(self.config),
            }

            engine = Engine(model_path=model_path, **params)

            self._load_tokenizer(AutoTokenizer, model_path, params)

            return engine

        self.engine = await self._run_in_executor(_load)

    def _load_tokenizer(self, tokenizer_class: Type[PreTrainedTokenizerBase], model_path: str, params: Dict[str, Any]) -> None:
        tokenizer_path = params.get("tokenizer_path") or model_path
        tokenizer_params: Dict[str, Any] = {}

        if params.get("trust_remote_code"):
            tokenizer_params["trust_remote_code"] = True

        if params.get("revision"):
            tokenizer_params["revision"] = params["revision"]

        self.tokenizer = tokenizer_class.from_pretrained(tokenizer_path, **tokenizer_params)

    async def _unload_model(self) -> None:
        if self.engine is not None:
            try:
                shutdown = getattr(self.engine, "shutdown", None)

                if callable(shutdown):
                    shutdown()
            except Exception:
                pass
            self.engine = None

        self.tokenizer = None

        try:
            import gc

            gc.collect()
        except Exception:
            pass

        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

    def _get_model_params(self, model: ModelConfig) -> Dict[str, Any]:
        params: Dict[str, Any] = {}

        if isinstance(model, HuggingfaceModelConfig):
            if model.revision is not None:
                params["revision"] = model.revision

            if model.cache_dir is not None:
                params["download_dir"] = model.cache_dir

        return params

    def _get_model_options(self, config: BaseModel) -> Dict[str, Any]:
        options: Dict[str, Any] = {}

        precision = getattr(config, "precision", None)

        if precision is not None:
            options["dtype"] = precision.value

        quantization = getattr(config, "quantization", None)

        if quantization is not None and quantization.type in _BITSANDBYTES_QUANT_TYPES:
            options["quantization"] = "bitsandbytes"

        engine_options = getattr(config, "options", None)

        if isinstance(engine_options, SglangEngineOptionsConfig):
            for field, value in engine_options.model_dump(exclude_none=True).items():
                options[field] = value

        return options
