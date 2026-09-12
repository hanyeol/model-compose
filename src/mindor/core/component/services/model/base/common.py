from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Mapping, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.component import ModelComponentConfig, ModelTaskType, ModelDriver, ModelConfig
from mindor.dsl.schema.action import ModelActionConfig
from mindor.dsl.schema.runtime import RuntimeType
from mindor.core.foundation import AsyncService
from mindor.core.logger import logging
from ....context import ComponentActionContext
from ..utils.provision import ModelProvisioner
from ..utils.device import DeviceResolver
import asyncio

if TYPE_CHECKING:
    import torch

class ModelTaskService(AsyncService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: ModelComponentConfig = config

        self._model_provisioner: ModelProvisioner = ModelProvisioner()
        self._device_resolver: DeviceResolver = DeviceResolver()
        self._model_loaded: bool = False
        self._model_load_lock: asyncio.Lock = asyncio.Lock()

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return []

    async def run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        if not self._model_loaded:
            async with self._model_load_lock:
                if not self._model_loaded:
                    await self._load_model_on_demand()

        return await self._run(action, context)

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
    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        pass

    async def _provision_model(self, model: ModelConfig, prefetch: bool = False) -> str:
        return await self._model_provisioner.provision(model, prefetch=prefetch)

    def _resolve_device(self, device: str) -> torch.device:
        return self._device_resolver.resolve(device)

    def _load_model_checkpoint(self, model: torch.nn.Module, model_path: str) -> None:
        checkpoint = torch.load(model_path, map_location="cpu")
        state_dict = self._get_state_dict_from_checkpoint(checkpoint)

        model.load_state_dict(state_dict, strict=True)

    def _get_state_dict_from_checkpoint(self, checkpoint: Any) -> Mapping[str, Any]:
        for key in [ "params", "state_dict" ]:
            if key in checkpoint:
                return checkpoint[key]
        return checkpoint

    def _require_isolated_runtime(self) -> None:
        # Some upstream packages carry version pins that can't coexist with the
        # host mindor stack. Refuse runtimes that share the host interpreter or
        # a plain subprocess of it, forcing the user onto virtualenv/docker.
        # `EMBEDDED` is the sentinel the worker sets on itself after entering
        # an already-isolated environment, so it's allowed through.
        runtime_type = self.config.runtime.type

        if runtime_type in (RuntimeType.NATIVE, RuntimeType.PROCESS):
            raise RuntimeError(
                f"Component '{self.id}' requires an isolated runtime; "
                f"got runtime.type = '{runtime_type.value}'."
            )

def register_model_task_service(type: ModelTaskType, driver: ModelDriver):
    def decorator(cls: Type[ModelTaskService]) -> Type[ModelTaskService]:
        if type not in ModelTaskServiceRegistry:
            ModelTaskServiceRegistry[type] = {}
        ModelTaskServiceRegistry[type][driver] = cls
        return cls
    return decorator

ModelTaskServiceRegistry: Dict[ModelTaskType, Dict[ModelDriver, Type[ModelTaskService]]] = {}
