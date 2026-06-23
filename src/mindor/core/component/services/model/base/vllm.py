from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from mindor.dsl.schema.component import ModelComponentConfig, HuggingfaceModelConfig, LocalModelConfig
from mindor.core.logger import logging
from .common import ModelTaskService

if TYPE_CHECKING:
    from vllm import AsyncLLMEngine
    from transformers.tokenization_utils_base import PreTrainedTokenizerBase

class VllmModelTaskService(ModelTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.engine: Optional[AsyncLLMEngine] = None
        self.tokenizer: Optional[PreTrainedTokenizerBase] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "vllm" ]

    async def _load_model(self) -> None:
        from vllm import AsyncEngineArgs, AsyncLLMEngine

        model_path = self._get_model_path()
        params = self._get_model_params()

        logging.info(f"Component '{self.id}': loading vLLM model from '{model_path}'")

        engine_args = AsyncEngineArgs(model=model_path, **params)
        self.engine = AsyncLLMEngine.from_engine_args(engine_args)

        self._load_tokenizer(model_path, params)

    def _load_tokenizer(self, model_path: str, params: Dict[str, Any]) -> None:
        from transformers import AutoTokenizer

        tokenizer_path = params.get("tokenizer") or model_path
        tokenizer_kwargs: Dict[str, Any] = {}

        if params.get("trust_remote_code"):
            tokenizer_kwargs["trust_remote_code"] = True
        if params.get("tokenizer_revision"):
            tokenizer_kwargs["revision"] = params["tokenizer_revision"]
        elif params.get("revision"):
            tokenizer_kwargs["revision"] = params["revision"]

        self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_path, **tokenizer_kwargs)

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

    def _get_model_path(self) -> str:
        if isinstance(self.config.model, HuggingfaceModelConfig):
            return self.config.model.repository

        if isinstance(self.config.model, LocalModelConfig):
            return self.config.model.path

        if isinstance(self.config.model, str):
            return self.config.model

        raise ValueError(f"Unknown model config type: {type(self.config.model)}")

    def _get_model_params(self) -> Dict[str, Any]:
        params: Dict[str, Any] = {}

        if isinstance(self.config.model, HuggingfaceModelConfig):
            if self.config.model.revision is not None:
                params["revision"] = self.config.model.revision
            if self.config.model.cache_dir is not None:
                params["download_dir"] = self.config.model.cache_dir
            if self.config.model.token is not None:
                params["hf_token"] = self.config.model.token

        precision = getattr(self.config, "precision", None)
        if precision is not None:
            params["dtype"] = self._map_precision(precision)

        quantization = getattr(self.config, "quantization", None)
        if quantization is not None:
            if hasattr(quantization, "type"):
                mapped = self._map_quantization(quantization.type)
                if mapped is not None:
                    params["quantization"] = mapped
            elif isinstance(quantization, str):
                params["quantization"] = quantization

        options = getattr(self.config, "options", None)
        if options is not None:
            for field, value in options.model_dump(exclude_none=True).items():
                params[field] = value

        return params

    def _map_precision(self, precision: Any) -> str:
        from mindor.dsl.schema.component import ModelPrecision

        mapping = {
            ModelPrecision.AUTO: "auto",
            ModelPrecision.FLOAT32: "float32",
            ModelPrecision.FLOAT16: "float16",
            ModelPrecision.BFLOAT16: "bfloat16",
        }
        return mapping.get(precision, "auto")

    def _map_quantization(self, q_type: Any) -> Optional[str]:
        from mindor.dsl.schema.component import ModelQuantizationType

        mapping = {
            ModelQuantizationType.INT8: "bitsandbytes",
            ModelQuantizationType.INT4: "bitsandbytes",
            ModelQuantizationType.FP4: "bitsandbytes",
            ModelQuantizationType.NF4: "bitsandbytes",
        }
        return mapping.get(q_type)
