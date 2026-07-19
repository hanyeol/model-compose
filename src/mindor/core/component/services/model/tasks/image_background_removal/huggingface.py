from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Optional, Dict, List, Any
from mindor.dsl.schema.action import ModelActionConfig, HuggingfaceImageBackgroundRemovalModelActionConfig
from mindor.dsl.schema.component import HuggingfaceImageBackgroundRemovalModelArchitecture, ModelComponentConfig, PeftAdapterConfig
from mindor.core.foundation.cancellation import CancellationToken
from ...base import ModelTaskType, ModelDriver, register_model_task_service
from ...base import ComponentActionContext
from ...base.huggingface.multimodal import HuggingfaceMultimodalModelTaskService
from .common import ImageBackgroundRemovalTaskAction
from PIL import Image as PILImage
import asyncio

if TYPE_CHECKING:
    from transformers import PreTrainedModel
    import torch

_IMAGENET_MEAN = (0.485, 0.456, 0.406)
_IMAGENET_STD  = (0.229, 0.224, 0.225)

class HuggingfaceImageBackgroundRemovalTaskAction(ImageBackgroundRemovalTaskAction):
    config: HuggingfaceImageBackgroundRemovalModelActionConfig

    def __init__(
        self,
        config: HuggingfaceImageBackgroundRemovalModelActionConfig,
        model: PreTrainedModel,
        device: torch.device,
    ):
        super().__init__(config, device)

        self.model: PreTrainedModel = model

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        input_size = await context.render_variable(self.config.params.input_size)

        params["input_size"] = int(input_size)

        return params

    def _predict_masks(
        self,
        images: List[PILImage.Image],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None
    ) -> List[PILImage.Image]:
        import torch
        from torchvision import transforms

        input_size = params["input_size"]

        transform = transforms.Compose([
            transforms.Resize((input_size, input_size)),
            transforms.ToTensor(),
            transforms.Normalize(_IMAGENET_MEAN, _IMAGENET_STD),
        ])

        batch = torch.stack([ transform(image) for image in images ]).to(self.device)

        with torch.inference_mode():
            outputs = self.model(batch)

        logits = outputs[-1] if isinstance(outputs, (list, tuple)) else outputs
        probs = torch.sigmoid(logits).squeeze(1).float().cpu()

        masks: List[PILImage.Image] = []
        for prob, image in zip(probs, images):
            mask_tensor = (prob * 255.0).clamp(0, 255).to(torch.uint8)
            mask = PILImage.fromarray(mask_tensor.numpy(), mode="L")
            if mask.size != image.size:
                mask = mask.resize(image.size, PILImage.Resampling.BILINEAR)
            masks.append(mask)

        return masks

@register_model_task_service(ModelTaskType.IMAGE_BACKGROUND_REMOVAL, ModelDriver.HUGGINGFACE)
class HuggingfaceImageBackgroundRemovalTaskService(HuggingfaceMultimodalModelTaskService):
    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "transformers", "torch", "torchvision", "accelerate", "timm", "kornia" ]

    async def _run(
        self,
        action: ModelActionConfig,
        context: ComponentActionContext,
        loop: asyncio.AbstractEventLoop
    ) -> Any:
        return await HuggingfaceImageBackgroundRemovalTaskAction(action, self.model, self.device).run(context, loop)

    def _get_model_class(self) -> Type[PreTrainedModel]:
        if self.config.architecture == HuggingfaceImageBackgroundRemovalModelArchitecture.AUTO:
            from transformers import AutoModelForImageSegmentation
            return AutoModelForImageSegmentation

        raise ValueError(f"Unknown architecture: {self.config.architecture}")

    def _get_model_params(self, config: Union[ModelComponentConfig, PeftAdapterConfig]) -> Dict[str, Any]:
        params = super()._get_model_params(config)

        params["trust_remote_code"] = True

        return params
