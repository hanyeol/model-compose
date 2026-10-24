from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Tuple, Type, Literal, Optional, Dict, List, Set, Annotated, Callable, Any
from pydantic import BaseModel
from mindor.dsl.schema.component import ModelComponentConfig, ModelConfig
from mindor.dsl.schema.component.impl.model.tasks.base.llamacpp import LlamaCppEngineOptionsConfig
from mindor.core.logger import logging
from .common import ModelTaskDriver

if TYPE_CHECKING:
    from llama_cpp import Llama

class LlamaCppModelTaskDriver(ModelTaskDriver):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[Llama] = None

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        return [ "llama-cpp-python", "huggingface_hub" ]

    async def _load_model(self) -> None:
        from llama_cpp import Llama

        model_path = await self._provision_model(self.config.model, prefetch=True)

        logging.info(f"Component '{self.id}': loading llama.cpp model from '{model_path}'")

        def _load() -> Llama:
            params: Dict[str, Any] = {
                **self._get_model_params(self.config.model),
                **self._get_model_options(self.config),
            }

            return Llama(model_path=model_path, **params)

        self.model = await self._run_in_executor(_load)

    async def _unload_model(self) -> None:
        self.model = None

    def _get_model_params(self, model: ModelConfig) -> Dict[str, Any]:
        return {}

    def _get_model_options(self, config: BaseModel) -> Dict[str, Any]:
        options: Dict[str, Any] = {}

        offload, main_gpu = self._resolve_gpu_offload(self.config.device)

        if offload:
            options["n_gpu_layers"] = -1

            if main_gpu is not None:
                options["main_gpu"] = main_gpu

        engine_options = getattr(config, "options", None)

        if isinstance(engine_options, LlamaCppEngineOptionsConfig):
            for field, value in engine_options.model_dump(exclude_none=True).items():
                options[field] = value

        options.setdefault("verbose", False)

        return options

    def _resolve_gpu_offload(self, device: str) -> Tuple[bool, Optional[int]]:
        if device in ("auto", "cuda", "mps"):
            return True, None

        if device == "cpu":
            return False, None

        device_type, _, device_index = device.partition(":")

        if device_type == "cuda" and device_index:
            try:
                return True, int(device_index)
            except ValueError:
                pass

        logging.warning(f"Invalid device '{device}', falling back to 'cpu'")

        return False, None
