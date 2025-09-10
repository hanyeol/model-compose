from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Mapping, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.component import ModelComponentConfig, ModelTaskType, ModelDriver, HuggingfaceModelConfig, LocalModelConfig
from mindor.dsl.schema.action import ModelActionConfig
from mindor.core.services import AsyncService
from mindor.core.logger import logging
from ....context import ComponentActionContext
import asyncio

if TYPE_CHECKING:
    import torch

class ModelTaskService(AsyncService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: ModelComponentConfig = config

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "torch" ]

    async def run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()

        async def _run():
            return await self._run(action, context, loop)

        return await self.run_in_thread(_run)

    @abstractmethod
    async def _run(self, action: ModelActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        pass

    def _get_model_path(self) -> str:
        if isinstance(self.config.model, HuggingfaceModelConfig):
            from .huggingface_hub import get_model_path
            return get_model_path(self.config.model)

        if isinstance(self.config.model, LocalModelConfig):
            return self.config.model.path
        
        if isinstance(self.config.model, str):
            return self.config.model

        raise ValueError(f"Unknown model config type: {type(self.config.model)}")

    def _resolve_device(self) -> torch.device:
        import torch

        try:
            return torch.device(self.config.device)
        except:
            logging.warning(f"Invalid device '{self.config.device}', falling back to 'cpu'")
        
        return torch.device("cpu")

    def _load_model_checkpoint(self, model: torch.nn.Module, model_path: str) -> None:
        checkpoint = torch.load(model_path, map_location="cpu")
        state_dict = self._get_state_dict_from_checkpoint(checkpoint)

        model.load_state_dict(state_dict, strict=True)

    def _get_state_dict_from_checkpoint(self, checkpoint: Any) -> Mapping[str, Any]:
        for key in [ "params", "state_dict" ]:
            if key in checkpoint:
                return checkpoint[key]
        return checkpoint

def register_model_task_service(type: ModelTaskType, driver: ModelDriver):
    def decorator(cls: Type[ModelTaskService]) -> Type[ModelTaskService]:
        if type not in ModelTaskServiceRegistry:
            ModelTaskServiceRegistry[type] = {}
        ModelTaskServiceRegistry[type][driver] = cls
        return cls
    return decorator

ModelTaskServiceRegistry: Dict[ModelTaskType, Dict[ModelDriver, Type[ModelTaskService]]] = {}
