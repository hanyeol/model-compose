from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Mapping, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.component import ModelComponentConfig, ModelTaskType, ModelDriver, HuggingfaceModelConfig, LocalModelConfig
from mindor.dsl.schema.action import ModelActionConfig
from mindor.core.foundation import AsyncService
from mindor.core.foundation.streaming.url import download_to_file
from mindor.core.logger import logging
from ....context import ComponentActionContext
from pathlib import Path
from urllib.parse import urlparse
import asyncio, os

if TYPE_CHECKING:
    import torch

class ModelTaskService(AsyncService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: ModelComponentConfig = config
        self._model_loaded: bool = False
        self._model_load_lock: asyncio.Lock = asyncio.Lock()

    def get_setup_requirements(self) -> Optional[List[str]]:
        return []

    async def run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        if not self._model_loaded:
            async with self._model_load_lock:
                if not self._model_loaded:
                    await self._load_model_on_demand()

        return await self.run_in_thread(self._run, action, context, asyncio.get_running_loop())

    async def _start(self) -> None:
        if self.config.preload:
            await self._load_model()
            self._model_loaded = True
        else:
            logging.info(f"Component '{self.id}': model will be loaded on demand")
        await super()._start()

    async def _stop(self) -> None:
        await super()._stop()

        if self._model_loaded:
            await self._unload_model()
            self._model_loaded = False

    async def _load_model_on_demand(self) -> None:
        logging.info(f"Component '{self.id}': loading model on demand...")
        await self._load_model()
        self._model_loaded = True

    @abstractmethod
    async def _load_model(self) -> None:
        pass

    @abstractmethod
    async def _unload_model(self) -> None:
        pass

    @abstractmethod
    async def _run(self, action: ModelActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        pass

    async def _resolve_local_model(
        self,
        default_url: Optional[str] = None,
        cache_dir: Optional[Path] = None,
        label: str = "model",
    ) -> str:
        path: Optional[str] = None
        url: Optional[str] = None

        if not isinstance(self.config.model, (LocalModelConfig, str)):
            raise ValueError(f"Unsupported model config type for {label}: {type(self.config.model).__name__}")

        path = self.config.model if isinstance(self.config.model, str) else self.config.model.path

        if path and os.path.exists(path):
            return path

        url = (self.config.model.url if isinstance(self.config.model, LocalModelConfig) else None) or default_url

        if not url:
            raise FileNotFoundError(f"{label} model not found: {path}")

        target = Path(path) if path else cache_dir / os.path.basename(urlparse(url).path)

        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            logging.info("Downloading %s model: %s", label, url)
            await download_to_file(url, target)

        return str(target)

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
