from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Optional, Dict, List, Any
from mindor.dsl.schema.action import ModelActionConfig, ImageEmbeddingModelActionConfig
from mindor.dsl.schema.component import HuggingfaceImageEmbeddingModelArchitecture
from mindor.core.foundation.cancellation import CancellationToken
from ...base import ModelTaskType, ModelDriver, register_model_task_service
from ...base import ComponentActionContext
from ...base.huggingface.multimodal import HuggingfaceMultimodalModelTaskService
from .common import ImageEmbeddingTaskAction
from PIL import Image as PILImage

if TYPE_CHECKING:
    from transformers import PreTrainedModel, ProcessorMixin
    from transformers.modeling_outputs import BaseModelOutput
    from torch import Tensor
    import torch

class HuggingfaceImageEmbeddingTaskAction(ImageEmbeddingTaskAction):
    def __init__(
        self,
        config: ImageEmbeddingModelActionConfig,
        architecture: HuggingfaceImageEmbeddingModelArchitecture,
        model: PreTrainedModel,
        processor: ProcessorMixin,
        device: torch.device,
    ):
        super().__init__(config)

        self.architecture: HuggingfaceImageEmbeddingModelArchitecture = architecture
        self.model: PreTrainedModel = model
        self.processor: ProcessorMixin = processor
        self.device: torch.device = device

    async def _embed_batch(
        self,
        images: List[PILImage.Image],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[List[float]]:
        def _embed() -> List[List[float]]:
            import torch, torch.nn.functional as F

            inputs: Dict[str, Tensor] = self.processor(images=images, return_tensors="pt")
            inputs = { key: value.to(self.device) for key, value in inputs.items() }

            with torch.inference_mode():
                embeddings = self._extract_image_features(inputs, params["pooling"])

            if params["normalize"]:
                embeddings = F.normalize(embeddings, p=2, dim=1, eps=1e-12)

            return embeddings.cpu().tolist()

        return await self._run_in_executor(_embed)

    def _extract_image_features(self, inputs: Dict[str, Tensor], pooling: str) -> Tensor:
        if self.architecture == HuggingfaceImageEmbeddingModelArchitecture.AUTO:
            # AUTO fell through to AutoModel — the concrete class is decided by
            # the model's own config.json. If it's a CLIP/SigLIP-family model
            # HuggingFace exposes a joint image projection via get_image_features;
            # otherwise pool the encoder's last_hidden_state.
            if hasattr(self.model, "get_image_features"):
                return self._resolve_image_features(self.model.get_image_features(**inputs), pooling)

            return self._pool_hidden_state(self.model(**inputs).last_hidden_state, pooling)

        if self.architecture == HuggingfaceImageEmbeddingModelArchitecture.CLIP:
            return self._resolve_image_features(self.model.get_image_features(**inputs), pooling)

        if self.architecture == HuggingfaceImageEmbeddingModelArchitecture.SIGLIP:
            return self._resolve_image_features(self.model.get_image_features(**inputs), pooling)

        if self.architecture == HuggingfaceImageEmbeddingModelArchitecture.DINOV2:
            return self._pool_hidden_state(self.model(**inputs).last_hidden_state, pooling)

        raise ValueError(f"Unknown architecture: {self.architecture}")

    def _resolve_image_features(self, features: Any, pooling: str) -> Tensor:
        # transformers 5.x returns BaseModelOutputWithPooling from get_image_features;
        # older versions return a bare tensor. Handle both.
        import torch

        if isinstance(features, torch.Tensor):
            return features

        if getattr(features, "pooler_output", None) is not None:
            return features.pooler_output

        if getattr(features, "last_hidden_state", None) is not None:
            return self._pool_hidden_state(features.last_hidden_state, pooling)

        raise ValueError(f"Cannot extract image features from output of type {type(features).__name__}")

    def _pool_hidden_state(self, last_hidden_state: Tensor, pooling: str) -> Tensor:
        import torch

        if pooling == "cls":
            return last_hidden_state[:, 0]

        if pooling == "mean":
            return torch.mean(last_hidden_state, dim=1)

        if pooling == "max":
            return torch.max(last_hidden_state, dim=1).values

        raise ValueError(f"Unsupported pooling type: {pooling}")

@register_model_task_service(ModelTaskType.IMAGE_EMBEDDING, ModelDriver.HUGGINGFACE)
class HuggingfaceImageEmbeddingTaskService(HuggingfaceMultimodalModelTaskService):
    def _get_model_class(self) -> Type[PreTrainedModel]:
        if self.config.architecture == HuggingfaceImageEmbeddingModelArchitecture.AUTO:
            from transformers import AutoModel
            return AutoModel

        if self.config.architecture == HuggingfaceImageEmbeddingModelArchitecture.CLIP:
            from transformers import CLIPModel
            return CLIPModel

        if self.config.architecture == HuggingfaceImageEmbeddingModelArchitecture.SIGLIP:
            from transformers import SiglipModel
            return SiglipModel

        if self.config.architecture == HuggingfaceImageEmbeddingModelArchitecture.DINOV2:
            from transformers import AutoModel
            return AutoModel

        raise ValueError(f"Unknown architecture: {self.config.architecture}")

    def _get_processor_class(self) -> Type[ProcessorMixin]:
        if self.config.architecture == HuggingfaceImageEmbeddingModelArchitecture.AUTO:
            from transformers import AutoImageProcessor
            return AutoImageProcessor

        if self.config.architecture == HuggingfaceImageEmbeddingModelArchitecture.CLIP:
            from transformers import CLIPProcessor
            return CLIPProcessor

        if self.config.architecture == HuggingfaceImageEmbeddingModelArchitecture.SIGLIP:
            from transformers import SiglipProcessor
            return SiglipProcessor

        if self.config.architecture == HuggingfaceImageEmbeddingModelArchitecture.DINOV2:
            from transformers import AutoImageProcessor
            return AutoImageProcessor

        raise ValueError(f"Unknown architecture: {self.config.architecture}")

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await HuggingfaceImageEmbeddingTaskAction(
            action,
            self.config.architecture,
            self.model,
            self.processor,
            self.device
        ).run(context)
