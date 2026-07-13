from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Generic, TypeVar, Optional, Dict, List, Tuple, Any
from mindor.dsl.schema.component import ModelComponentConfig, HuggingfaceModelConfig
from mindor.core.logger import logging
from ..common import ModelTaskService

if TYPE_CHECKING:
    from diffusers import DiffusionPipeline
    import torch

TMethod = TypeVar("TMethod")

class HuggingfaceDiffusionPipelineTaskService(ModelTaskService, Generic[TMethod]):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.pipelines: Optional[Dict[TMethod, DiffusionPipeline]] = None
        self.device: Optional[torch.device] = None

    async def _load_model(self) -> None:
        methods = list({ action.method for action in self.config.actions })
        self.pipelines, self.device = self._load_pretrained_pipelines(methods)

    async def _unload_model(self) -> None:
        self.pipelines = None
        self.device = None

    def _load_pretrained_pipelines(self, methods: List[TMethod]) -> Tuple[Dict[TMethod, DiffusionPipeline], torch.device]:
        device = self._resolve_device(self.config.device)

        params = self._get_pipeline_params()
        params["torch_dtype"] = self._get_pipeline_dtype(device)

        source = self._get_pipeline_source()

        base_pipeline_cls = self._get_pipeline_class(None)
        logging.info(f"Component '{self.id}': loading {base_pipeline_cls.__name__} from {source}")
        base_pipeline = base_pipeline_cls.from_pretrained(source, **params).to(device)

        pipelines: Dict[TMethod, DiffusionPipeline] = {}

        for method in methods:
            pipeline_cls = self._get_pipeline_class(method)

            if pipeline_cls is base_pipeline_cls:
                pipelines[method] = base_pipeline
            else:
                logging.info(f"Component '{self.id}': deriving {pipeline_cls.__name__} from {base_pipeline_cls.__name__}")
                pipelines[method] = pipeline_cls.from_pipe(base_pipeline)

        return pipelines, device

    def _get_pipeline_class(self, method: Optional[TMethod]) -> Type[DiffusionPipeline]:
        raise NotImplementedError("Pipeline class loader not implemented.")

    def _get_pipeline_source(self) -> str:
        if isinstance(self.config.model, HuggingfaceModelConfig):
            return self.config.model.repository

        return self.config.model.path

    def _get_pipeline_params(self) -> Dict[str, Any]:
        params: Dict[str, Any] = {}

        if isinstance(self.config.model, HuggingfaceModelConfig):
            if self.config.model.revision:
                params["revision"] = self.config.model.revision
            if self.config.model.cache_dir:
                params["cache_dir"] = self.config.model.cache_dir
            if self.config.model.token:
                params["token"] = self.config.model.token
            if self.config.model.local_files_only:
                params["local_files_only"] = bool(self.config.model.local_files_only)

        return params

    def _get_pipeline_dtype(self, device: torch.device) -> torch.dtype:
        import torch

        if device.type in ("cuda", "mps"):
            return self._get_accelerated_dtype()

        return torch.float32

    def _get_accelerated_dtype(self) -> torch.dtype:
        import torch

        return torch.bfloat16
