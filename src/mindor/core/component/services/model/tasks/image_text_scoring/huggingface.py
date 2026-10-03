from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Optional, Dict, List, Any
from mindor.dsl.schema.action import ModelActionConfig, ImageTextScoringModelActionConfig
from mindor.dsl.schema.component import HuggingfaceImageTextScoringModelArchitecture
from mindor.core.foundation.cancellation import CancellationToken
from ...base import ModelTaskType, ModelDriverType, register_model_task_driver
from ...base import ComponentActionContext
from ...base.huggingface.multimodal import HuggingfaceMultimodalModelTaskDriver
from .common import ImageTextScoringTaskAction
from PIL import Image as PILImage

if TYPE_CHECKING:
    from transformers import PreTrainedModel, ProcessorMixin
    from torch import Tensor
    import torch

class HuggingfaceImageTextScoringTaskAction(ImageTextScoringTaskAction):
    def __init__(
        self,
        config: ImageTextScoringModelActionConfig,
        model: PreTrainedModel,
        processor: ProcessorMixin,
        device: torch.device,
    ):
        super().__init__(config)

        self.model: PreTrainedModel = model
        self.processor: ProcessorMixin = processor
        self.device: torch.device = device

    async def _score(
        self,
        images: List[PILImage.Image],
        texts: List[str],
        mode: str,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        def _score() -> Dict[str, Any]:
            cosines, logits = self._forward(images, texts)

            if mode == "pairwise":
                return self._build_pairwise_result(cosines, logits, params)

            return self._build_cross_result(cosines, logits, mode, params)

        return await self._run_in_executor(_score)

    def _forward(self, images: List[PILImage.Image], texts: List[str]) -> tuple[Tensor, Optional[Tensor]]:
        """Return (cosines, logits) as N_img × N_text tensors. logits is None if the model has no logit_scale."""
        import torch

        inputs = self.processor(images=images, text=texts, return_tensors="pt", padding=True, truncation=True)
        inputs = { key: value.to(self.device) for key, value in inputs.items() }

        with torch.inference_mode():
            outputs = self.model(**inputs)
            logits = getattr(outputs, "logits_per_image", None)
            logit_scale = getattr(self.model, "logit_scale", None)

            if logits is not None and logit_scale is not None:
                cosines = logits / logit_scale.exp()
                return cosines.detach().cpu(), logits.detach().cpu()

            # Fallback: compute cosines from projected features directly.
            image_features = self._as_tensor(self.model.get_image_features(pixel_values=inputs["pixel_values"]))
            text_features = self._as_tensor(self.model.get_text_features(
                input_ids=inputs["input_ids"],
                attention_mask=inputs.get("attention_mask", None),
            ))
            image_features = image_features / image_features.norm(p=2, dim=-1, keepdim=True).clamp(min=1e-12)
            text_features = text_features / text_features.norm(p=2, dim=-1, keepdim=True).clamp(min=1e-12)
            cosines = image_features @ text_features.T

            return cosines.detach().cpu(), None

    def _build_pairwise_result(self, cosines: Tensor, logits: Optional[Tensor], params: Dict[str, Any]) -> Dict[str, Any]:
        # Diagonal: (image[index], text[index]) scores.
        length = cosines.shape[0]
        cosine_values = [ float(cosines[index][index]) for index in range(length) ]
        logit_values = [ float(logits[index][index]) for index in range(length) ] if logits is not None else None

        if length == 1:
            result: Dict[str, Any] = { "cosine": cosine_values[0] }

            if params["return_logit"] and logit_values is not None:
                result["logit"] = logit_values[0]

            return result
        else:
            result = { "cosine": cosine_values }

            if params["return_logit"] and logit_values is not None:
                result["logit"] = logit_values

            return result

    def _build_cross_result(self, cosines: Tensor, logits: Optional[Tensor], mode: str, params: Dict[str, Any]) -> Dict[str, Any]:
        import torch

        # Softmax is always normalized along the many-axis — the row/column with
        # more than one element. The one-length axis would collapse to [1.0, ...].
        if mode == "texts_to_image":
            # 1 image × N texts → row across the text axis.
            cosine_row = cosines[0]
            logit_row = logits[0] if logits is not None else None
            softmax_row = torch.softmax(logit_row, dim=-1) if logit_row is not None and params["return_softmax"] else None
        else:
            # N images × 1 text → column across the image axis.
            cosine_row = cosines[:, 0]
            logit_row = logits[:, 0] if logits is not None else None
            softmax_row = torch.softmax(logit_row, dim=-1) if logit_row is not None and params["return_softmax"] else None

        result: Dict[str, Any] = { "cosine": [ float(cosine) for cosine in cosine_row.tolist() ] }

        if params["return_logit"] and logit_row is not None:
            result["logit"] = [ float(logit) for logit in logit_row.tolist() ]

        if softmax_row is not None:
            result["softmax"] = [ float(prob) for prob in softmax_row.tolist() ]

        return result

    def _as_tensor(self, features: Any) -> Tensor:
        import torch

        if isinstance(features, torch.Tensor):
            return features

        if getattr(features, "pooler_output", None) is not None:
            return features.pooler_output

        if getattr(features, "last_hidden_state", None) is not None:
            return features.last_hidden_state[:, 0]

        raise ValueError(f"Cannot extract projected features from output of type {type(features).__name__}")

@register_model_task_driver(ModelTaskType.IMAGE_TEXT_SCORING, ModelDriverType.HUGGINGFACE)
class HuggingfaceImageTextScoringTaskDriver(HuggingfaceMultimodalModelTaskDriver):
    def _get_model_class(self) -> Type[PreTrainedModel]:
        if self.config.architecture == HuggingfaceImageTextScoringModelArchitecture.CLIP:
            from transformers import CLIPModel
            return CLIPModel

        if self.config.architecture == HuggingfaceImageTextScoringModelArchitecture.SIGLIP:
            from transformers import SiglipModel
            return SiglipModel

        raise ValueError(f"Unknown architecture: {self.config.architecture}")

    def _get_processor_class(self) -> Type[ProcessorMixin]:
        if self.config.architecture == HuggingfaceImageTextScoringModelArchitecture.CLIP:
            from transformers import CLIPProcessor
            return CLIPProcessor

        if self.config.architecture == HuggingfaceImageTextScoringModelArchitecture.SIGLIP:
            from transformers import SiglipProcessor
            return SiglipProcessor

        raise ValueError(f"Unknown architecture: {self.config.architecture}")

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await HuggingfaceImageTextScoringTaskAction(
            action,
            self.model,
            self.processor,
            self.device,
        ).run(context)
