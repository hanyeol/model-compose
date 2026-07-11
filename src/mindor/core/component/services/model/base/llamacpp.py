from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from mindor.dsl.schema.component import ModelComponentConfig, HuggingfaceModelConfig, LocalModelConfig
from mindor.dsl.schema.component.impl.model.tasks.base.llamacpp import LlamaCppEngineOptionsConfig
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

        if self.config.device != "cpu":
            params["n_gpu_layers"] = -1

        options = getattr(self.config, "options", None)
        if isinstance(options, LlamaCppEngineOptionsConfig):
            for field, value in options.model_dump(exclude_none=True).items():
                params[field] = value

        params.setdefault("verbose", False)

        return params
