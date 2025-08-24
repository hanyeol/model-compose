from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.component import ModelComponentConfig, ModelTaskType, ModelSourceConfig, DeviceMode
from mindor.dsl.schema.action import ModelActionConfig
from mindor.core.services import AsyncService
from ...context import ComponentActionContext
from transformers import PreTrainedModel, PreTrainedTokenizer, ProcessorMixin
import torch, asyncio

class ModelTaskService(AsyncService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: ModelComponentConfig = config

    async def run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()

        async def _run():
            return await self._run(action, context, loop)

        return await self.run_in_thread(_run)

    @abstractmethod
    async def _run(self, action: ModelActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        pass

    def _load_pretrained_model(self, extra_params: Optional[Dict[str, Any]] = None) -> Union[PreTrainedModel, torch.nn.Module]:
        params = self._get_common_model_params()

        if extra_params:
            params.update(extra_params)

        model = self._get_model_class().from_pretrained(self.config.model, **params)

        if self.config.device_mode == DeviceMode.SINGLE:
            model = model.to(torch.device(self.config.device))

        return model

    def _get_common_model_params(self) -> Dict[str, Any]:
        params: Dict[str, Any] = {}

        if isinstance(self.config.model, ModelSourceConfig):
            if self.config.model.revision:
                params["revision"] = self.config.model.revision

        if self.config.device_mode != DeviceMode.SINGLE:
            params["device_map"] = self.config.device_mode.value
    
        if self.config.precision is not None:
            params["torch_dtype"] = getattr(torch, self.config.precision.value)
    
        if self.config.low_cpu_mem_usage:
            params["low_cpu_mem_usage"] = True

        if self.config.cache_dir:
            params["cache_dir"] = self.config.cache_dir

        if self.config.local_files_only:
            params["local_files_only"] = True

        return params

    def _get_model_class(self) -> Type[PreTrainedModel]:
        raise NotImplementedError("Model class loader not implemented.")

    def _load_pretrained_tokenizer(self, extra_params: Optional[Dict[str, Any]] = None) -> PreTrainedTokenizer:
        params = self._get_common_tokenizer_params()
 
        if extra_params:
            params.update(extra_params)

        return self._get_tokenizer_class().from_pretrained(self.config.model, **params)

    def _get_common_tokenizer_params(self) -> Dict[str, Any]:
        params: Dict[str, Any] = {}

        if isinstance(self.config.model, ModelSourceConfig):
            if self.config.model.revision:
                params["revision"] = self.config.model.revision
    
        if not self.config.fast_tokenizer:
            params["use_fast"] = False

        if self.config.cache_dir:
            params["cache_dir"] = self.config.cache_dir

        if self.config.local_files_only:
            params["local_files_only"] = True

        return params

    def _get_tokenizer_class(self) -> Type[PreTrainedTokenizer]:
        raise NotImplementedError("Tokenizer class loader not implemented.")

    def _load_pretrained_processor(self, extra_params: Optional[Dict[str, Any]] = None) -> ProcessorMixin:
        params = self._get_common_processor_params()
 
        if extra_params:
            params.update(extra_params)

        return self._get_processor_class().from_pretrained(self.config.model, **params)

    def _get_common_processor_params(self) -> Dict[str, Any]:
        params: Dict[str, Any] = {}

        if isinstance(self.config.model, ModelSourceConfig):
            if self.config.model.revision:
                params["revision"] = self.config.model.revision
 
        if self.config.cache_dir:
            params["cache_dir"] = self.config.cache_dir

        if self.config.local_files_only:
            params["local_files_only"] = True

        return params

    def _get_processor_class(self) -> Type[ProcessorMixin]:
        raise NotImplementedError("Processor class loader not implemented.")

    def _get_model_device(self, model: PreTrainedModel) -> torch.device:
        return next(model.parameters()).device

def register_model_task_service(type: ModelTaskType):
    def decorator(cls: Type[ModelTaskService]) -> Type[ModelTaskService]:
        ModelTaskServiceRegistry[type] = cls
        return cls
    return decorator

ModelTaskServiceRegistry: Dict[ModelTaskType, Type[ModelTaskService]] = {}
