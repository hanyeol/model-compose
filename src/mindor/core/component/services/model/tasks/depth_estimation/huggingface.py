from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Optional, Dict, List, Any
from mindor.dsl.schema.action import ModelActionConfig, HuggingfaceDepthEstimationModelActionConfig
from mindor.dsl.schema.component import HuggingfaceDepthEstimationModelArchitecture
from mindor.core.foundation.cancellation import CancellationToken
from ...base import ModelTaskType, ModelDriverType, register_model_task_driver
from ...base import ComponentActionContext
from ...base.huggingface.multimodal import HuggingfaceMultimodalModelTaskDriver
from .common import DepthEstimationTaskAction
from PIL import Image as PILImage

if TYPE_CHECKING:
    from transformers import PreTrainedModel, ProcessorMixin
    import torch

class HuggingfaceDepthEstimationTaskAction(DepthEstimationTaskAction):
    config: HuggingfaceDepthEstimationModelActionConfig

    def __init__(
        self,
        config: HuggingfaceDepthEstimationModelActionConfig,
        model: PreTrainedModel,
        processor: ProcessorMixin,
        device: torch.device,
    ):
        super().__init__(config, device)

        self.model: PreTrainedModel = model
        self.processor: ProcessorMixin = processor

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        image_size = await context.render_scalar(self.config.params.image_size, int)

        params.update({
            "image_size": image_size,
        })

        return params

    async def _estimate_batch(
        self,
        images: List[PILImage.Image],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[PILImage.Image]:
        images = self._preprocess_images(images)

        def _predict_depths() -> List[PILImage.Image]:
            import torch
            import torch.nn.functional as F

            processor_params: Dict[str, Any] = { "images": images, "return_tensors": "pt" }

            if params["image_size"] is not None:
                processor_params["size"] = { "height": params["image_size"], "width": params["image_size"] }

            inputs = self.processor(**processor_params)
            inputs = { key: value.to(self.device) for key, value in inputs.items() }

            with torch.inference_mode():
                outputs = self.model(**inputs)

            predicted_depth = outputs.predicted_depth

            if predicted_depth.ndim == 3:
                predicted_depth = predicted_depth.unsqueeze(1)

            depths: List[PILImage.Image] = []

            for depth, image in zip(predicted_depth, images):
                depth_map = F.interpolate(
                    depth.unsqueeze(0),
                    size=(image.height, image.width),
                    mode="bicubic",
                    align_corners=False,
                ).squeeze()

                depth_min = depth_map.min()
                depth_max = depth_map.max()

                if depth_max > depth_min:
                    depth_map = (depth_map - depth_min) / (depth_max - depth_min)
                else:
                    depth_map = torch.zeros_like(depth_map)

                if params["invert"]:
                    depth_map = 1.0 - depth_map

                depth_u8 = (depth_map * 255.0).clamp(0, 255).to(torch.uint8).cpu().numpy()
                depths.append(PILImage.fromarray(depth_u8, mode="L"))

            return depths

        return await self._run_in_executor(_predict_depths)

    def _preprocess_images(self, images: List[PILImage.Image]) -> List[PILImage.Image]:
        return [ image.convert("RGB") for image in images ]

@register_model_task_driver(ModelTaskType.DEPTH_ESTIMATION, ModelDriverType.HUGGINGFACE)
class HuggingfaceDepthEstimationTaskDriver(HuggingfaceMultimodalModelTaskDriver):
    def _get_model_class(self) -> Type[PreTrainedModel]:
        if self.config.architecture == HuggingfaceDepthEstimationModelArchitecture.AUTO:
            from transformers import AutoModelForDepthEstimation
            return AutoModelForDepthEstimation

        if self.config.architecture == HuggingfaceDepthEstimationModelArchitecture.DPT:
            from transformers import DPTForDepthEstimation
            return DPTForDepthEstimation

        if self.config.architecture == HuggingfaceDepthEstimationModelArchitecture.DEPTH_ANYTHING:
            from transformers import AutoModelForDepthEstimation
            return AutoModelForDepthEstimation

        raise ValueError(f"Unknown architecture: {self.config.architecture}")

    def _get_processor_class(self) -> Type[ProcessorMixin]:
        from transformers import AutoImageProcessor
        return AutoImageProcessor

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await HuggingfaceDepthEstimationTaskAction(action, self.model, self.processor, self.device).run(context)
