from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from mindor.dsl.schema.component import ModelComponentConfig, HuggingfaceModelConfig, LocalModelConfig
from mindor.core.logger import logging
from .common import ModelTaskService

if TYPE_CHECKING:
    from llama_cpp import Llama

class LlamaCppModelTaskService(ModelTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[Llama] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "llama-cpp-python", "huggingface_hub" ]

    async def _load_model(self) -> None:
        from llama_cpp import Llama

        model_path = self._get_model_path()
        params = self._get_model_params()

        logging.info(f"Component '{self.id}': loading llama.cpp model from '{model_path}'")
        self.model = Llama(model_path=model_path, **params)

    async def _unload_model(self) -> None:
        self.model = None

    def _get_model_path(self) -> str:
        if isinstance(self.config.model, HuggingfaceModelConfig):
            from .huggingface_hub import get_model_path
            return get_model_path(self.config.model)

        if isinstance(self.config.model, LocalModelConfig):
            return self.config.model.path

        if isinstance(self.config.model, str):
            return self.config.model

        raise ValueError(f"Unknown model config type: {type(self.config.model)}")

    def _get_model_params(self) -> Dict[str, Any]:
        params: Dict[str, Any] = {}

        n_gpu_layers = getattr(self.config, "n_gpu_layers", None)
        if n_gpu_layers is not None:
            params["n_gpu_layers"] = n_gpu_layers
        else:
            device = getattr(self.config, "device", "cpu")
            if device != "cpu":
                params["n_gpu_layers"] = -1

        n_ctx = getattr(self.config, "context_length", None)
        if n_ctx is not None:
            params["n_ctx"] = n_ctx

        n_batch = getattr(self.config, "n_batch", None)
        if n_batch is not None:
            params["n_batch"] = n_batch

        n_threads = getattr(self.config, "n_threads", None)
        if n_threads is not None:
            params["n_threads"] = n_threads

        verbose = getattr(self.config, "verbose", False)
        params["verbose"] = bool(verbose)

        return params
