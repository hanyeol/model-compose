from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Set, Annotated, Mapping, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.component import ModelComponentConfig, ModelTaskType, ModelDriverType, ModelConfig, ModelPrecision
from mindor.dsl.schema.action import ModelActionConfig
from mindor.core.foundation.async_service import AsyncService
from mindor.core.foundation.package.torch import is_torch_installed, empty_torch_cache
from mindor.core.component.base import ComponentDriver
from mindor.core.logger import logging
from ....action.base import ComponentAction
from ....context import ComponentActionContext
from ..utils.provision import ModelProvisioner
from ..utils.device import DeviceResolver, DeviceSpec
import asyncio

if TYPE_CHECKING:
    from contextlib import AbstractContextManager
    import torch

class ModelTaskComponentAction(ComponentAction):
    def _autocast_context(
        self,
        device: Optional[torch.device],
        precision: Optional[ModelPrecision],
    ) -> AbstractContextManager:
        """``torch.autocast`` for float16/bfloat16; no-op otherwise.

        Model weights stay in float32 so fp16-unsafe paths (STFT/FFT, certain
        conv kernels) remain intact; only autocast-eligible ops run reduced.
        Narrows to cuda — mps and cpu autocast are not uniformly validated
        across the custom checkpoints we wrap.
        """
        from contextlib import nullcontext
        import torch

        if precision not in (ModelPrecision.FLOAT16, ModelPrecision.BFLOAT16):
            return nullcontext()

        if device is None or device.type != "cuda":
            return nullcontext()

        dtype = torch.float16 if precision == ModelPrecision.FLOAT16 else torch.bfloat16

        return torch.autocast(device_type="cuda", dtype=dtype)

class ModelTaskDriver(ComponentDriver):
    config: ModelComponentConfig

    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self._model_provisioner: ModelProvisioner = ModelProvisioner()
        self._device_resolver: DeviceResolver = DeviceResolver()
        self._model_loaded: bool = False
        self._model_load_lock: asyncio.Lock = asyncio.Lock()

    @property
    def model_loaded(self) -> bool:
        return self._model_loaded

    async def load_model(self) -> None:
        async with self._model_load_lock:
            if not self._model_loaded:
                await self._load_model()
                self._model_loaded = True

    async def unload_model(self) -> None:
        async with self._model_load_lock:
            if self._model_loaded:
                try:
                    await self._unload_model()
                    self._model_loaded = False
                finally:
                    await self._reclaim_device_memory()

    async def run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        if not self._model_loaded:
            await self._load_model_on_demand()

        if getattr(action, "peft_adapter", None):
            self._apply_peft_adapters(action.peft_adapter)
        else:
            self._disable_peft_adapters()

        return await self._run(action, context)

    async def _load_model_on_demand(self) -> None:
        async with self._model_load_lock:
            if not self._model_loaded:
                logging.info(f"Component '{self.id}': loading model on demand...")

                await self._load_model()
                self._model_loaded = True

    async def _provision_model(self, model: ModelConfig, prefetch: bool = False) -> str:
        return await self._model_provisioner.provision(model, prefetch=prefetch)

    def _resolve_device(self, device: str, use_torch: bool = True) -> Union[torch.device, DeviceSpec]:
        return self._device_resolver.resolve(device, use_torch=use_torch)

    def _resolve_torch_dtype(self, precision: ModelPrecision) -> torch.dtype:
        import torch

        if precision == ModelPrecision.FLOAT8_E4M3:
            return getattr(torch, "float8_e4m3fn", None) or getattr(torch, "float8_e4m3")

        if precision == ModelPrecision.FLOAT8_E5M2:
            return getattr(torch, "float8_e5m2")

        return getattr(torch, precision.value)

    def _load_model_checkpoint(self, model: torch.nn.Module, model_path: str) -> None:
        import torch

        checkpoint = torch.load(model_path, map_location="cpu")
        state_dict = self._get_state_dict_from_checkpoint(checkpoint)

        model.load_state_dict(state_dict, strict=True)

    def _get_state_dict_from_checkpoint(self, checkpoint: Mapping[str, Any]) -> Mapping[str, Any]:
        for key in [ "params", "state_dict" ]:
            if key in checkpoint:
                return checkpoint[key]

        return checkpoint

    def _apply_peft_adapters(self, adapters: List[Any]) -> None:
        # Overridden by drivers that support PEFT adapters.
        pass

    def _disable_peft_adapters(self) -> None:
        # Overridden by drivers that support PEFT adapters.
        pass

    async def _reclaim_device_memory(self) -> None:
        import gc

        gc.collect()

        if is_torch_installed():
            empty_torch_cache()

    @abstractmethod
    async def _load_model(self) -> None:
        pass

    @abstractmethod
    async def _unload_model(self) -> None:
        pass

    @abstractmethod
    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_model_task_driver(type: ModelTaskType, driver: ModelDriverType):
    def decorator(cls: Type[ModelTaskDriver]) -> Type[ModelTaskDriver]:
        if type not in ModelTaskDriverRegistry:
            ModelTaskDriverRegistry[type] = {}
        ModelTaskDriverRegistry[type][driver] = cls
        return cls
    return decorator

ModelTaskDriverRegistry: Dict[ModelTaskType, Dict[ModelDriverType, Type[ModelTaskDriver]]] = {}
