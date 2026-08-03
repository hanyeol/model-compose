from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Generic, TypeVar, Optional, Dict, List, Tuple, Any
from mindor.dsl.schema.component import ModelComponentConfig, ModelConfig
from mindor.core.logger import logging
from .base import HuggingfaceModelTaskService

if TYPE_CHECKING:
    from diffusers import DiffusionPipeline
    import torch

TMethod = TypeVar("TMethod")

class HuggingfaceDiffusionPipelineTaskService(HuggingfaceModelTaskService, Generic[TMethod]):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.pipelines: Optional[Dict[Optional[TMethod], DiffusionPipeline]] = None
        self.device: Optional[torch.device] = None

    async def _load_model(self) -> None:
        methods = list({ getattr(action, "method", None) for action in self.config.actions })
        self.pipelines, self.device = await self._load_pretrained_pipelines(methods)

    async def _unload_model(self) -> None:
        self.pipelines = None
        self.device = None

    async def _load_pretrained_pipelines(self, methods: List[Optional[TMethod]]) -> Tuple[Dict[Optional[TMethod], DiffusionPipeline], torch.device]:
        model_path = await self._provision_model(self.config.model)
        device = self._resolve_device(self.config.device)
        dtype = self._get_pipeline_dtype(device)

        params = self._get_model_params(self.config.model)
        params["torch_dtype"] = dtype

        submodules = await self._load_pipeline_submodules(device, dtype)

        if submodules:
            params.update(submodules)

        base_pipeline_cls = self._get_pipeline_class(None)
        logging.info(f"Component '{self.id}': loading {base_pipeline_cls.__name__} from {model_path}")
        base_pipeline = base_pipeline_cls.from_pretrained(model_path, **params).to(device)

        pipelines: Dict[Optional[TMethod], DiffusionPipeline] = {}

        for method in methods:
            pipeline_cls = self._get_pipeline_class(method)

            if pipeline_cls is base_pipeline_cls:
                pipelines[method] = base_pipeline
            else:
                logging.info(f"Component '{self.id}': deriving {pipeline_cls.__name__} from {base_pipeline_cls.__name__}")
                pipelines[method] = pipeline_cls.from_pipe(base_pipeline)

        return pipelines, device

    async def _load_pipeline_submodules(self, device: torch.device, dtype: torch.dtype) -> Dict[str, Any]:
        return {}

    def _get_pipeline_class(self, method: Optional[TMethod]) -> Type[DiffusionPipeline]:
        raise NotImplementedError("Pipeline class loader not implemented.")

    def _get_pipeline_dtype(self, device: torch.device) -> torch.dtype:
        import torch

        if device.type in ("cuda", "mps"):
            return self._get_accelerated_dtype()

        return torch.float32

    def _get_accelerated_dtype(self) -> torch.dtype:
        import torch

        return torch.bfloat16
