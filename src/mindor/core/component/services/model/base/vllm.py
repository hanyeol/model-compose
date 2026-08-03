from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from pydantic import BaseModel
from mindor.dsl.schema.component import ModelComponentConfig, ModelConfig, HuggingfaceModelConfig, ModelQuantizationType
from mindor.dsl.schema.component.impl.model.tasks.base.vllm import VllmEngineOptionsConfig
from mindor.core.logger import logging
from .common import ModelTaskService

if TYPE_CHECKING:
    from vllm import AsyncLLMEngine
    from transformers.tokenization_utils_base import PreTrainedTokenizerBase

_BITSANDBYTES_QUANT_TYPES = {
    ModelQuantizationType.INT8,
    ModelQuantizationType.INT4,
    ModelQuantizationType.FP4,
    ModelQuantizationType.NF4,
}

class VllmModelTaskService(ModelTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.engine: Optional[AsyncLLMEngine] = None
        self.tokenizer: Optional[PreTrainedTokenizerBase] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "vllm" ]

    async def _load_model(self) -> None:
        from vllm import AsyncEngineArgs, AsyncLLMEngine

        model_path = await self._provision_model(self.config.model)
        params = self._get_model_params(self.config.model)
        options = self._get_model_options(self.config)

        if options:
            params.update(options)

        logging.info(f"Component '{self.id}': loading vLLM model from '{model_path}'")

        engine_args = AsyncEngineArgs(model=model_path, **params)
        self.engine = AsyncLLMEngine.from_engine_args(engine_args)

        self._load_tokenizer(model_path, params)

    def _load_tokenizer(self, model_path: str, params: Dict[str, Any]) -> None:
        from transformers import AutoTokenizer

        tokenizer_path = params.get("tokenizer") or model_path
        tokenizer_params: Dict[str, Any] = {}

        if params.get("trust_remote_code"):
            tokenizer_params["trust_remote_code"] = True
        if params.get("tokenizer_revision"):
            tokenizer_params["revision"] = params["tokenizer_revision"]
        elif params.get("revision"):
            tokenizer_params["revision"] = params["revision"]

        self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_path, **tokenizer_params)

    async def _unload_model(self) -> None:
        if self.engine is not None:
            try:
                shutdown = getattr(self.engine, "shutdown_background_loop", None)
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

            if model.token is not None:
                params["hf_token"] = model.token

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

        if isinstance(engine_options, VllmEngineOptionsConfig):
            for field, value in engine_options.model_dump(exclude_none=True).items():
                options[field] = value

        return options
