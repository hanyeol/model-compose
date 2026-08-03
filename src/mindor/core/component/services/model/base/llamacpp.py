from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from pydantic import BaseModel
from mindor.dsl.schema.component import ModelComponentConfig, ModelConfig
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

        model_path = await self._provision_model(self.config.model, prefetch=True)
        params = self._get_model_params(self.config.model)
        options = self._get_model_options(self.config)

        if options:
            params.update(options)

        logging.info(f"Component '{self.id}': loading llama.cpp model from '{model_path}'")
        self.model = Llama(model_path=model_path, **params)

    async def _unload_model(self) -> None:
        self.model = None

    def _get_model_params(self, model: ModelConfig) -> Dict[str, Any]:
        return {}

    def _get_model_options(self, config: BaseModel) -> Dict[str, Any]:
        options: Dict[str, Any] = {}

        if self._resolve_device(self.config.device).type != "cpu":
            options["n_gpu_layers"] = -1

        engine_options = getattr(config, "options", None)

        if isinstance(engine_options, LlamaCppEngineOptionsConfig):
            for field, value in engine_options.model_dump(exclude_none=True).items():
                options[field] = value

        options.setdefault("verbose", False)

        return options
